#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PROJECT_DIR}/src/backend"
FRONTEND_DIR="${PROJECT_DIR}/src/frontend"
RUNTIME_DIR="${PROJECT_DIR}/src/.data/run"
SERVICE_LOG_DIR="${PROJECT_DIR}/src/.data/logs/services"
BACKEND_PID_FILE="${RUNTIME_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/frontend.pid"
BACKEND_LOG="${SERVICE_LOG_DIR}/backend.log"
FRONTEND_LOG="${SERVICE_LOG_DIR}/frontend.log"
BACKEND_PORT="8000"
FRONTEND_PORT="5173"
BACKEND_HOST="127.0.0.1"
FRONTEND_HOST="127.0.0.1"
START_TIMEOUT="${DATAWEAVE_START_TIMEOUT:-30}"

mkdir -p "${RUNTIME_DIR}" "${SERVICE_LOG_DIR}"

info() {
  printf '\033[1;32m[DataWeave]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[DataWeave]\033[0m %s\n' "$*" >&2
}

fail() {
  printf '\033[1;31m[DataWeave]\033[0m %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"
}

read_pid() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    tr -dc '0-9' < "${pid_file}"
  fi
  return 0
}

group_is_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 -- "-${pid}" 2>/dev/null
}

stop_managed_group() {
  local service_name="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "${pid_file}")"
  if [[ -z "${pid}" ]]; then
    rm -f "${pid_file}"
    return
  fi
  if ! group_is_alive "${pid}"; then
    rm -f "${pid_file}"
    return
  fi
  if ! matches_service "${service_name}" "${pid}"; then
    warn "${pid_file} 中的 PID 已不属于 DataWeave ${service_name}，仅清理过期 PID 文件。"
    rm -f "${pid_file}"
    return
  fi

  info "正在停止 ${service_name}（进程组 ${pid}）..."
  kill -TERM -- "-${pid}" 2>/dev/null || true
  for _ in {1..20}; do
    if ! group_is_alive "${pid}"; then
      rm -f "${pid_file}"
      return
    fi
    sleep 0.25
  done
  warn "${service_name} 未在 5 秒内退出，执行强制停止。"
  kill -KILL -- "-${pid}" 2>/dev/null || true
  rm -f "${pid_file}"
}

matches_service() {
  local service_name="$1"
  local pid="$2"
  local command_line cwd
  command_line="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
  if [[ "${service_name}" == "后端" ]]; then
    [[ "${command_line}" == *"dataweave.main:app"* ]] || [[ "${command_line}" == *"${BACKEND_DIR}"* ]]
  else
    [[ "${command_line}" == *"${FRONTEND_DIR}"* ]] || {
      [[ "${cwd}" == "${FRONTEND_DIR}" ]] && [[ "${command_line}" == *"vite"* || "${command_line}" == *"npm run dev"* ]]
    }
  fi
}

collect_process_tree() {
  local root_pid="$1"
  local child
  printf '%s\n' "${root_pid}"
  while read -r child; do
    [[ -n "${child}" ]] || continue
    collect_process_tree "${child}"
  done < <(pgrep -P "${root_pid}" 2>/dev/null || true)
}

stop_process_tree() {
  local root_pid="$1"
  local -a process_ids=()
  mapfile -t process_ids < <(collect_process_tree "${root_pid}")
  ((${#process_ids[@]} > 0)) || return
  kill -TERM "${process_ids[@]}" 2>/dev/null || true
  for _ in {1..20}; do
    local alive=0 process_id
    for process_id in "${process_ids[@]}"; do
      if kill -0 "${process_id}" 2>/dev/null; then
        alive=1
        break
      fi
    done
    ((alive == 0)) && return
    sleep 0.25
  done
  kill -KILL "${process_ids[@]}" 2>/dev/null || true
}

stop_matching_port_process() {
  local service_name="$1"
  local port="$2"
  local pid candidate parent
  local -a listeners=()
  mapfile -t listeners < <(lsof -nP -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u)
  for pid in "${listeners[@]}"; do
    [[ -n "${pid}" ]] || continue
    if ! matches_service "${service_name}" "${pid}"; then
      fail "端口 ${port} 已被非 DataWeave 进程占用（PID ${pid}），为避免误杀已停止启动。"
    fi
    candidate="${pid}"
    while true; do
      parent="$(ps -p "${candidate}" -o ppid= 2>/dev/null | tr -d ' ' || true)"
      [[ "${parent}" =~ ^[0-9]+$ ]] || break
      ((parent > 1)) || break
      matches_service "${service_name}" "${parent}" || break
      candidate="${parent}"
    done
    info "发现手动启动的 DataWeave ${service_name}（PID ${candidate}），正在停止..."
    stop_process_tree "${candidate}"
  done
}

stop_all() {
  stop_managed_group "前端" "${FRONTEND_PID_FILE}"
  stop_managed_group "后端" "${BACKEND_PID_FILE}"
  stop_matching_port_process "前端" "${FRONTEND_PORT}"
  stop_matching_port_process "后端" "${BACKEND_PORT}"
  info "DataWeave 服务已停止。"
}

ensure_dependencies() {
  require_command curl
  require_command lsof
  require_command pgrep
  require_command ps
  require_command readlink
  require_command setsid

  if [[ ! -x "${BACKEND_DIR}/.venv/bin/uvicorn" ]]; then
    require_command uv
    info "正在安装后端依赖..."
    (
      cd "${BACKEND_DIR}"
      uv sync --extra dev
    )
  fi
  if [[ ! -x "${FRONTEND_DIR}/node_modules/.bin/vite" ]]; then
    require_command npm
    info "正在安装前端依赖..."
    (
      cd "${FRONTEND_DIR}"
      npm install
    )
  fi
}

wait_for_url() {
  local service_name="$1"
  local url="$2"
  local pid="$3"
  local log_file="$4"
  local elapsed=0
  while ((elapsed < START_TIMEOUT * 4)); do
    if curl --silent --fail --max-time 1 "${url}" >/dev/null 2>&1; then
      info "${service_name}已就绪：${url}"
      return
    fi
    if ! group_is_alive "${pid}"; then
      warn "${service_name}启动进程已退出，最近日志如下："
      tail -n 30 "${log_file}" >&2 || true
      return 1
    fi
    sleep 0.25
    ((elapsed += 1))
  done
  warn "${service_name}启动超时，最近日志如下："
  tail -n 30 "${log_file}" >&2 || true
  return 1
}

start_all() {
  ensure_dependencies
  printf '\n===== %s DataWeave backend restart =====\n' "$(date --iso-8601=seconds)" >> "${BACKEND_LOG}"
  (
    cd "${BACKEND_DIR}"
    exec setsid "${BACKEND_DIR}/.venv/bin/uvicorn" dataweave.main:app --reload --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
  ) >> "${BACKEND_LOG}" 2>&1 &
  local backend_pid=$!
  printf '%s\n' "${backend_pid}" > "${BACKEND_PID_FILE}"

  printf '\n===== %s DataWeave frontend restart =====\n' "$(date --iso-8601=seconds)" >> "${FRONTEND_LOG}"
  (
    cd "${FRONTEND_DIR}"
    exec setsid "${FRONTEND_DIR}/node_modules/.bin/vite" --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
  ) >> "${FRONTEND_LOG}" 2>&1 &
  local frontend_pid=$!
  printf '%s\n' "${frontend_pid}" > "${FRONTEND_PID_FILE}"

  if ! wait_for_url "后端" "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" "${backend_pid}" "${BACKEND_LOG}"; then
    stop_all
    fail "后端启动失败或未在 ${START_TIMEOUT} 秒内就绪。"
  fi
  if ! wait_for_url "前端" "http://${FRONTEND_HOST}:${FRONTEND_PORT}/" "${frontend_pid}" "${FRONTEND_LOG}"; then
    stop_all
    fail "前端启动失败或未在 ${START_TIMEOUT} 秒内就绪。"
  fi

  printf '\n'
  info "DataWeave 已启动完成"
  printf '  前端页面： http://%s:%s/\n' "${FRONTEND_HOST}" "${FRONTEND_PORT}"
  printf '  API 文档： http://%s:%s/docs\n' "${BACKEND_HOST}" "${BACKEND_PORT}"
  printf '  后端日志： %s\n' "${BACKEND_LOG}"
  printf '  前端日志： %s\n' "${FRONTEND_LOG}"
}

show_status() {
  local backend_pid frontend_pid
  backend_pid="$(read_pid "${BACKEND_PID_FILE}")"
  frontend_pid="$(read_pid "${FRONTEND_PID_FILE}")"
  if group_is_alive "${backend_pid}"; then
    info "后端运行中（进程组 ${backend_pid}，端口 ${BACKEND_PORT}）"
  else
    warn "后端未运行"
  fi
  if group_is_alive "${frontend_pid}"; then
    info "前端运行中（进程组 ${frontend_pid}，端口 ${FRONTEND_PORT}）"
  else
    warn "前端未运行"
  fi
}

main() {
  local action="${1:-restart}"
  case "${action}" in
    start|restart)
      stop_all
      start_all
      ;;
    stop)
      stop_all
      ;;
    status)
      show_status
      ;;
    *)
      fail "未知操作：${action}。可用操作：restart（默认）、start、stop、status。"
      ;;
  esac
}

main "$@"
