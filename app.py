"""News summarizer API - FA23-BDS-054 - ABC News Australia.

GET /get?keyword=<word>
Selenium (headless Chrome) searches ABC News Australia, opens the first
news article in the results, summarizes it and returns JSON.
"""
import re
import threading
from collections import Counter
from urllib.parse import quote_plus

from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

REGISTRATION = "FA23-BDS-054"
NEWS_SOURCE = "ABC News Australia"
SEARCH_URL = "https://www.abc.net.au/news/search?query={}"
# ABC news articles look like https://www.abc.net.au/news/2026-10-28/some-title/107315006
ARTICLE_RE = re.compile(r"^https://www\.abc\.net\.au/news/\d{4}-\d{2}-\d{2}/[^/]+/\d+$")
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

app = Flask(__name__)
chrome_lock = threading.Lock()  # one Chrome at a time (small server)


def make_driver():
    opts = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--window-size=1366,900",
                "--blink-settings=imagesEnabled=false",
                f"--user-agent={USER_AGENT}"):
        opts.add_argument(arg)
    opts.page_load_strategy = "eager"
    driver = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=opts)
    driver.set_page_load_timeout(45)
    return driver


def first_article_url(driver, keyword):
    """Search ABC News and return the first news-article link in the results."""
    driver.get(SEARCH_URL.format(quote_plus(keyword)))

    def find_link(d):
        hrefs = d.execute_script(
            "return Array.from(document.querySelectorAll('a[href]'), a => a.href);")
        for href in hrefs:
            clean = href.split("#")[0].split("?")[0]
            if ARTICLE_RE.match(clean):
                return clean
        return False

    try:
        return WebDriverWait(driver, 25).until(find_link)
    except TimeoutException:
        return None


def article_paragraphs(driver, url):
    """Open the article and return its text paragraphs."""
    driver.get(url)
    WebDriverWait(driver, 20).until(
        lambda d: d.execute_script("return document.querySelectorAll('article p').length > 3;"))
    paras = driver.execute_script(
        "return Array.from(document.querySelectorAll('article p'), p => p.innerText.trim());")
    return [p for p in paras if len(p) > 60][:30]


STOPWORDS = set("""a an the and or but if of to in on at by for with from as is are was
were be been being it its this that these those he she they we you i his her their our
your has have had do does did not no will would can could should may might also said says
than then there here what which who whom when where why how into about over after before
more most such just one two new year years""".split())


def summarize(paragraphs, max_sentences=4):
    """Extractive summary: keep the sentences with the most important words."""
    text = " ".join(paragraphs)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 6]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOPWORDS and len(w) > 2]
    freq = Counter(words)
    top = max(freq.values())

    def score(sentence):
        ws = [w for w in re.findall(r"[a-z']+", sentence.lower()) if w in freq]
        return sum(freq[w] / top for w in ws) / (len(ws) + 1)

    best = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
    return " ".join(sentences[i] for i in sorted(best[:max_sentences]))


@app.get("/")
def home():
    return f"""<!doctype html><html><head><title>News Summarizer - {REGISTRATION}</title></head>
<body style="font-family:sans-serif;max-width:700px;margin:40px auto">
<h1>News Summarizer API</h1>
<p><b>Registration:</b> {REGISTRATION}<br><b>News source:</b> {NEWS_SOURCE}</p>
<form action="/get"><input name="keyword" placeholder="keyword" required>
<button>Summarize</button></form>
<p>Example: <code>/get?keyword=climate</code></p></body></html>"""


@app.get("/get")
def get_summary():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify(error="query parameter 'keyword' is required"), 400

    result = {"registration": REGISTRATION, "newssource": NEWS_SOURCE,
              "keyword": keyword, "url": "", "summary": ""}
    with chrome_lock:
        driver = None
        try:
            driver = make_driver()
            url = first_article_url(driver, keyword)
            if not url:
                result["summary"] = "No news article found for this keyword."
            else:
                result["url"] = url
                result["summary"] = summarize(article_paragraphs(driver, url)) or \
                    "Article found but no text could be extracted."
        except (TimeoutException, WebDriverException) as exc:
            result["summary"] = f"Scraping failed: {type(exc).__name__}"
        finally:
            if driver:
                driver.quit()
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
