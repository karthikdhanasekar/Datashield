"""
DataShield OSINT - Elasticsearch Service
Indexes findings for fast full-text search and analytics
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

INDEX_PREFIX = settings.ELASTICSEARCH_INDEX_PREFIX
FINDINGS_INDEX = f"{INDEX_PREFIX}_findings"
SCANS_INDEX    = f"{INDEX_PREFIX}_scans"


async def get_es_client():
    """Get async Elasticsearch client."""
    try:
        from elasticsearch import AsyncElasticsearch
        client = AsyncElasticsearch(
            hosts=[settings.ELASTICSEARCH_URL],
            request_timeout=10,
            retry_on_timeout=True,
            max_retries=3,
        )
        return client
    except ImportError:
        logger.warning("elasticsearch package not available")
        return None


async def ensure_indices() -> None:
    """Create Elasticsearch indices with mappings if they don't exist."""
    client = await get_es_client()
    if not client:
        return

    findings_mapping = {
        "mappings": {
            "properties": {
                "id":               {"type": "keyword"},
                "user_id":          {"type": "keyword"},
                "scan_id":          {"type": "keyword"},
                "finding_type":     {"type": "keyword"},
                "source_domain":    {"type": "keyword"},
                "source_url":       {"type": "text"},
                "source_title":     {"type": "text", "analyzer": "standard"},
                "severity":         {"type": "keyword"},
                "risk_score":       {"type": "float"},
                "description":      {"type": "text", "analyzer": "standard"},
                "exposed_data_types": {"type": "keyword"},
                "snippet":          {"type": "text"},
                "is_removed":       {"type": "boolean"},
                "is_false_positive":{"type": "boolean"},
                "discovered_at":    {"type": "date"},
            }
        }
    }

    try:
        if not await client.indices.exists(index=FINDINGS_INDEX):
            await client.indices.create(index=FINDINGS_INDEX, body=findings_mapping)
            logger.info("Created findings index", index=FINDINGS_INDEX)
    except Exception as e:
        logger.error("Failed to create ES index", error=str(e))
    finally:
        await client.close()


async def index_finding(finding_data: Dict[str, Any]) -> bool:
    """Index a single finding in Elasticsearch."""
    client = await get_es_client()
    if not client:
        return False

    try:
        await client.index(
            index=FINDINGS_INDEX,
            id=finding_data.get("id"),
            document=finding_data,
        )
        return True
    except Exception as e:
        logger.error("Failed to index finding", error=str(e), id=finding_data.get("id"))
        return False
    finally:
        await client.close()


async def search_findings(
    user_id: str,
    query: str,
    severity: Optional[str] = None,
    finding_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Full-text search across findings for a user."""
    client = await get_es_client()
    if not client:
        return {"hits": [], "total": 0}

    must_clauses = [
        {"term": {"user_id": user_id}},
        {"term": {"is_false_positive": False}},
    ]

    if query:
        must_clauses.append({
            "multi_match": {
                "query": query,
                "fields": ["description", "source_title", "snippet", "source_domain"],
                "fuzziness": "AUTO",
            }
        })

    if severity:
        must_clauses.append({"term": {"severity": severity}})
    if finding_type:
        must_clauses.append({"term": {"finding_type": finding_type}})

    body = {
        "query": {"bool": {"must": must_clauses}},
        "sort": [{"risk_score": "desc"}, {"discovered_at": "desc"}],
        "from": (page - 1) * page_size,
        "size": page_size,
        "highlight": {
            "fields": {
                "description": {},
                "snippet": {},
            }
        }
    }

    try:
        result = await client.search(index=FINDINGS_INDEX, body=body)
        hits = result["hits"]["hits"]
        total = result["hits"]["total"]["value"]
        return {
            "hits": [{"_id": h["_id"], **h["_source"], "highlights": h.get("highlight", {})} for h in hits],
            "total": total,
        }
    except Exception as e:
        logger.error("ES search failed", error=str(e))
        return {"hits": [], "total": 0}
    finally:
        await client.close()


async def get_exposure_aggregations(user_id: str) -> Dict[str, Any]:
    """Get aggregated exposure statistics for a user from Elasticsearch."""
    client = await get_es_client()
    if not client:
        return {}

    body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"user_id": user_id}},
                    {"term": {"is_false_positive": False}},
                    {"term": {"is_removed": False}},
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_severity": {
                "terms": {"field": "severity"}
            },
            "by_type": {
                "terms": {"field": "finding_type"}
            },
            "by_domain": {
                "terms": {"field": "source_domain", "size": 10}
            },
            "over_time": {
                "date_histogram": {
                    "field": "discovered_at",
                    "calendar_interval": "week",
                }
            }
        }
    }

    try:
        result = await client.search(index=FINDINGS_INDEX, body=body)
        return result.get("aggregations", {})
    except Exception as e:
        logger.error("ES aggregation failed", error=str(e))
        return {}
    finally:
        await client.close()
