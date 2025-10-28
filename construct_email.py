from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import datetime
import time
from loguru import logger
from llm import get_llm
import tiktoken
import re

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
  </table>
  """
  return block_template

def get_summary_html(summary_en: str, summary_zh: str):
  """Generate HTML block for daily summary"""
  summary_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 2px solid #4CAF50; border-radius: 8px; padding: 20px; background-color: #f0f8f0; margin-bottom: 20px;">
  <tr>
    <td style="font-size: 22px; font-weight: bold; color: #2E7D32; margin-bottom: 12px;">
        📊 Daily Summary | 每日总结
    </td>
  </tr>
  <tr>
    <td style="font-size: 15px; color: #333; padding: 12px 0; line-height: 1.6;">
        <strong>EN:</strong> {summary_en}
    </td>
  </tr>
  <tr>
    <td style="font-size: 15px; color: #333; padding: 12px 0; line-height: 1.6;">
        <strong>ZH:</strong> {summary_zh}
    </td>
  </tr>
  </table>
  """
  return summary_template.format(summary_en=summary_en, summary_zh=summary_zh)

def get_block_html(title:str, authors:str, rate:str,arxiv_id:str, abstract:dict, pdf_url:str, code_url:str=None, affiliations:str=None):
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>' if code_url else ''

    # Handle both dict (bilingual) and str (legacy) formats
    if isinstance(abstract, dict):
        tldr_html = f'<strong>EN:</strong> {abstract.get("en", "")}<br><strong>ZH:</strong> {abstract.get("zh", "")}'
    else:
        tldr_html = abstract

    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
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
            <strong>arXiv ID:</strong> <a href="https://arxiv.org/abs/{arxiv_id}" target="_blank">{arxiv_id}</a>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0; line-height: 1.6;">
            <strong>TLDR:</strong><br>{tldr_html}
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
    return block_template.format(title=title, authors=authors,rate=rate,arxiv_id=arxiv_id, tldr_html=tldr_html, pdf_url=pdf_url, code=code, affiliations=affiliations)

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


def generate_daily_summary(papers: list[ArxivPaper]) -> dict[str, str]:
    """Generate an overall summary of today's papers in both English and Chinese"""
    if len(papers) == 0:
        return {"en": "No papers today.", "zh": "今日无论文。"}

    logger.info("Generating daily summary...")

    # Collect all paper information (titles + abstracts)
    paper_info = []
    for p in papers:
        paper_info.append(f"Title: {p.title}\nAbstract: {p.summary}\nScore: {p.score:.2f}\n")

    papers_text = "\n---\n".join(paper_info)

    prompt = f"""Based on the following {len(papers)} recommended arXiv papers, provide a brief summary (3-5 sentences) covering:
1. Main research areas and topics
2. Notable trends, themes, or emerging directions
3. Highlight 2-3 most interesting papers worth special attention

Format your response exactly as:
EN: [English summary in 3-5 sentences]
ZH: [中文总结，3-5句话]

Papers:
{papers_text}
"""

    # Truncate to avoid token limits
    enc = tiktoken.encoding_for_model("gpt-4o")
    prompt_tokens = enc.encode(prompt)
    # Use larger context for summary since we're processing all papers
    prompt_tokens = prompt_tokens[:12000]  # 12k tokens should be enough for summary
    prompt = enc.decode(prompt_tokens)

    llm = get_llm()
    summary_text = llm.generate(
        messages=[
            {
                "role": "system",
                "content": "You are an expert research assistant who synthesizes academic papers and identifies key trends. Provide insightful summaries in multiple languages.",
            },
            {"role": "user", "content": prompt},
        ]
    )

    # Parse the bilingual response
    result = {"en": "", "zh": ""}
    try:
        en_match = re.search(r'EN:\s*(.+?)(?=\nZH:|$)', summary_text, re.DOTALL)
        zh_match = re.search(r'ZH:\s*(.+?)$', summary_text, re.DOTALL)

        if en_match:
            result["en"] = en_match.group(1).strip()
        if zh_match:
            result["zh"] = zh_match.group(1).strip()

        # Fallback
        if not result["en"] and not result["zh"]:
            result["en"] = summary_text.strip()
            result["zh"] = summary_text.strip()
    except Exception as e:
        logger.warning(f"Failed to parse daily summary: {e}")
        result["en"] = summary_text.strip()
        result["zh"] = summary_text.strip()

    return result


def render_email(papers:list[ArxivPaper]):
    parts = []
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html())

    # Generate daily summary at the beginning
    daily_summary = generate_daily_summary(papers)
    summary_html = get_summary_html(daily_summary["en"], daily_summary["zh"])

    for p in tqdm(papers,desc='Rendering Email'):
        rate = get_stars(p.score)
        author_list = [a.name for a in p.authors]
        num_authors = len(author_list)

        if num_authors <= 5:
            authors = ', '.join(author_list)
        else:
            authors = ', '.join(author_list[:3] + ['...'] + author_list[-2:])
        if p.affiliations is not None:
            affiliations = p.affiliations[:5]
            affiliations = ', '.join(affiliations)
            if len(p.affiliations) > 5:
                affiliations += ', ...'
        else:
            affiliations = 'Unknown Affiliation'
        parts.append(get_block_html(p.title, authors,rate,p.arxiv_id ,p.tldr, p.pdf_url, p.code_url, affiliations))
        time.sleep(10)

    content = summary_html + '<br>' + '</br><br>'.join(parts) + '</br>'
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
