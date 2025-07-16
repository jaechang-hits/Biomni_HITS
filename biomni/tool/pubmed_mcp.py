import os
from typing import List, Optional
from Bio import Entrez
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

Entrez.email = os.getenv("NCBI_EMAIL") or "YOUR_EMAIL"
mcp = FastMCP("pubmed-live")


class Article(BaseModel):
    pmid: str
    title: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None
    abstract: Optional[str] = None


@mcp.tool()
def search_pubmed(query: str, max_results: int = 10) -> List[Article]:
    ids = Entrez.read(Entrez.esearch(db="pubmed", term=query, retmax=max_results))["IdList"]
    summaries = Entrez.read(Entrez.esummary(db="pubmed", id=",".join(ids))) if ids else []
    articles: List[Article] = []
    for s in summaries:
        articles.append(Article(
            pmid=s["Id"],
            title=s["Title"],
            journal=s.get("FullJournalName", ""),
            year=s.get("PubDate", "")[:4]
        ))
    return articles


@mcp.tool()
def get_article_abstract(pmid: str) -> str:
    with Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="text") as h:
        return h.read()


if __name__ == "__main__":
    mcp.run()