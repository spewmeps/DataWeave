from __future__ import annotations

from dataweave.schemas import TemplateElement, TemplateResponse


def paper_analysis_template() -> TemplateResponse:
    elements = [
        TemplateElement(
            key="paper.title",
            label="论文标题",
            type="string",
            required=True,
            section_hints=["title"],
            guideline="保留论文原始标题，不翻译或改写。",
        ),
        TemplateElement(
            key="paper.authors",
            label="作者",
            type="list",
            required=True,
            section_hints=["title", "metadata"],
            guideline="按署名顺序提取个人或机构作者。",
        ),
        TemplateElement(
            key="paper.affiliations",
            label="作者机构与国家",
            type="list",
            section_hints=["title", "metadata", "author_footnotes"],
            guideline="保留机构原文，并拆分部门、机构、城市和国家。",
        ),
        TemplateElement(
            key="paper.publication_date",
            label="主要发表时间",
            type="object",
            section_hints=["metadata", "header", "footer"],
            guideline="保留日期类型、来源和原始精度。",
        ),
        TemplateElement(
            key="paper.author_keywords",
            label="作者关键词",
            type="list",
            section_hints=["keywords", "metadata", "abstract"],
            guideline="提取作者在论文中明确给出的关键词，保留原文及顺序；未提供时返回空列表。",
        ),
        TemplateElement(
            key="research.domain_keywords",
            label="领域关键词",
            type="list",
            required=True,
            section_hints=["title", "abstract", "introduction"],
            guideline="提取 3–8 个可标识学科、技术子领域和研究问题的规范化关键词，并绑定支持证据。",
        ),
        TemplateElement(
            key="research.innovation_keywords",
            label="创新关键词",
            type="list",
            required=True,
            section_hints=["introduction", "method", "conclusion"],
            guideline="提取 3–8 个可标识新方法、新机制、架构或优化点的关键词，只依据作者明确声明的创新。",
        ),
        TemplateElement(
            key="research.problem",
            label="研究问题",
            type="string",
            required=True,
            section_hints=["abstract", "introduction"],
            guideline="提取作者明确要解决的问题。",
        ),
        TemplateElement(
            key="research.contributions",
            label="核心贡献",
            type="list",
            required=True,
            section_hints=["introduction", "conclusion"],
            guideline="优先提取作者列举的贡献项。",
        ),
        TemplateElement(
            key="method.summary",
            label="方法概述",
            type="string",
            required=True,
            section_hints=["abstract", "method", "architecture"],
            guideline="说明核心机制和处理流程，不加入外部解释。",
        ),
        TemplateElement(
            key="experiments.datasets",
            label="实验数据集",
            type="list",
            section_hints=["experiment", "setup"],
            guideline="保留数据集名称和划分方式。",
        ),
        TemplateElement(
            key="experiments.results",
            label="实验结果",
            type="list",
            required=True,
            section_hints=["results", "tables", "experiment"],
            guideline="数值和单位保持原样，并绑定实验条件。",
        ),
        TemplateElement(
            key="paper.limitations",
            label="局限性",
            type="list",
            section_hints=["limitations", "conclusion", "discussion"],
            guideline="只提取作者明确披露的局限。",
        ),
    ]
    return TemplateResponse(
        id="paper_analysis",
        name="论文结构化分析",
        version=3,
        description="提取论文元数据、领域与创新关键词、研究问题、方法、实验和局限，并绑定原文证据。",
        elements=elements,
    )

