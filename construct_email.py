from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import datetime
from loguru import logger

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  """
  return block_template

def get_daily_summary(papers: list[ArxivPaper]) -> str:
    """生成今日论文简报

    Args:
        papers (list[ArxivPaper]): 论文列表

    Returns:
        str: HTML 格式的今日简报
    """
    if not papers:
        return ""

    # 为每篇论文生成引用标记
    paper_refs = {p.arxiv_id: f'[{i+1}]' for i, p in enumerate(papers)}

    prompt = """分析以下论文列表，生成一份今日简报（500字左右），要求：
    1. 总结论文的主题分布和研究热点
    2. 分析论文之间的关联性和研究脉络
    3. 突出重要发现和潜在影响
    4. 对未来研究方向进行展望
    5. 在提到具体论文时，使用 [ID] 标记（例如：[1]、[2]）

    论文列表：
    """
    for i, p in enumerate(papers, 1):
        prompt += f"\n论文 [{i}]:\n"
        prompt += f"标题：{p.title}\n"
        prompt += f"英文摘要：{p.paper_analysis['tldr_en']}\n"
        prompt += f"中文摘要：{p.paper_analysis['tldr_zh']}\n"
        prompt += f"详细分析：{p.paper_analysis['detailed_analysis']}\n"
        if p.affiliations:
            prompt += f"研究机构：{', '.join(p.affiliations)}\n"

    llm = get_llm()
    try:
        summary = llm.generate(
            messages=[
                {
                    "role": "system",
                    "content": """你是一个专业的科技论文分析师，擅长：
                    1. 发现论文之间的关联性和研究脉络
                    2. 识别领域发展趋势和创新点
                    3. 评估研究工作的潜在影响
                    4. 预测未来研究方向
                    请确保在分析中引用具体论文的编号。""",
                },
                {"role": "user", "content": prompt},
            ]
        )
    except Exception as e:
        logger.error(f"Failed to generate daily summary: {e}")
        summary = "今日简报生成失败"

    # 将论文引用替换为可点击的链接
    for arxiv_id, ref in paper_refs.items():
        summary = summary.replace(ref, f'<a href="#{arxiv_id}" style="color: #1a73e8; text-decoration: none; font-weight: bold;">{ref}</a>')

    template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f0f7ff; margin-bottom: 20px;">
        <tr>
            <td style="font-size: 24px; font-weight: bold; color: #1a73e8; padding-bottom: 12px;">
                📰 今日论文简报
            </td>
        </tr>
        <tr>
            <td style="font-size: 16px; color: #333; line-height: 1.8;">
                {summary}
            </td>
        </tr>
    </table>
    """
    return template.format(summary=summary)

def get_block_html(title:str, authors:str, rate:str, arxiv_id:str, paper_analysis:dict, pdf_url:str, code_url:str=None, affiliations:str=None):
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>' if code_url else ''
    
    # 使用 details/summary 标签实现折叠功能
    detailed_analysis = f"""
    <details style="margin-top: 12px;">
        <summary style="cursor: pointer; color: #1a73e8; font-weight: bold;">
            📝 详细解读
        </summary>
        <div style="margin-top: 8px; padding: 12px; background-color: #f8f9fa; border-radius: 4px; line-height: 1.6;">
            {paper_analysis['detailed_analysis']}
        </div>
    </details>
    """

    block_template = """
    <table id="{arxiv_id}" border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            <br>
            <i>{affiliations}</i>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {rate}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>arXiv ID:</strong> {arxiv_id}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <div style="margin-bottom: 8px;">
                <strong>English TLDR:</strong> {tldr_en}
            </div>
            <div style="margin-bottom: 8px;">
                <strong>中文 TLDR:</strong> {tldr_zh}
            </div>
            {detailed_analysis}
        </td>
    </tr>
    <tr>
        <td style="padding: 8px 0;">
            <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">PDF</a>
            {code}
        </td>
    </tr>
    </table>
    """
    return block_template.format(
        title=title,
        authors=authors,
        rate=rate,
        arxiv_id=arxiv_id,
        tldr_en=paper_analysis.get('tldr_en', 'Failed to generate English TLDR'),
        tldr_zh=paper_analysis.get('tldr_zh', '无法生成中文摘要'),
        detailed_analysis=detailed_analysis,
        pdf_url=pdf_url,
        code=code,
        affiliations=affiliations
    )

def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(papers:list[ArxivPaper]):
    parts = []
    if len(papers) == 0:
        return framework.replace('__CONTENT__', get_empty_html())
    
    # 添加今日简报
    daily_summary = get_daily_summary(papers)
    parts.append(daily_summary)
    
    for p in tqdm(papers,desc='Rendering Email'):
        rate = get_stars(p.score)
        authors = [a.name for a in p.authors[:5]]
        authors = ', '.join(authors)
        if len(p.authors) > 5:
            authors += ', ...'
        if p.affiliations is not None:
            affiliations = p.affiliations[:5]
            affiliations = ', '.join(affiliations)
            if len(p.affiliations) > 5:
                affiliations += ', ...'
        else:
            affiliations = 'Unknown Affiliation'
        parts.append(get_block_html(
            p.title,
            authors,
            rate,
            p.arxiv_id,
            p.paper_analysis,
            p.pdf_url,
            p.code_url,
            affiliations
        ))

    content = '<br>' + '</br><br>'.join(parts) + '</br>'
    return framework.replace('__CONTENT__', content)

def send_email(sender:str, receiver:str, password:str,smtp_server:str,smtp_port:int, html:str,):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('Github Action <%s>' % sender)
    msg['To'] = _format_addr('You <%s>' % receiver)
    today = datetime.datetime.now().strftime('%Y/%m/%d')
    msg['Subject'] = Header(f'Daily arXiv {today}', 'utf-8').encode()

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    except Exception as e:
        logger.warning(f"Failed to use TLS. {e}")
        logger.warning(f"Try to use SSL.")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    server.login(sender, password)
    server.sendmail(sender, [receiver], msg.as_string())
    server.quit()