"""
=============================================================================
Article Manager - DocketWatch Articles Table Integration
=============================================================================
Purpose: Helper module for managing articles table operations.
         Provides Python interface to articles stored procedures.

Author: DocketWatch Development Team
Date: 2025-10-15

Usage:
    from article_manager import upsert_article_for_event, get_todays_article
    
    article_id = upsert_article_for_event(
        cursor=cursor,
        fk_case=12345,
        event_id='event-guid',
        event_date='2025-10-15',
        story_headline='Breaking News',
        story_body='Story content...',
        ai_model='gemini-2.5-flash',
        ai_tokens_input=1000,
        ai_tokens_output=500,
        ai_cost=0.00123
    )

Dependencies:
    - pyodbc
    - Phase 2 stored procedures (upsert_article_for_event, complete_article)
=============================================================================
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def upsert_article_for_event(
    cursor,
    fk_case: int,
    event_id: str,  # GUID as string
    event_date: date,
    story_headline: Optional[str] = None,
    story_sub_head: Optional[str] = None,
    story_body: Optional[str] = None,
    image_url: Optional[str] = None,
    ai_model: Optional[str] = None,
    ai_prompt: Optional[str] = None,
    ai_tokens_input: Optional[int] = None,
    ai_tokens_output: Optional[int] = None,
    ai_cost: Optional[float] = None,
    generated_by: str = 'pipeline'
) -> Optional[str]:
    """
    Create or update the single Pending article for a case on a given day.
    
    This calls the dbo.upsert_article_for_event stored procedure which:
    - Finds existing Pending article for case/date OR creates new one
    - Updates story content and increments version
    - Links the case_event to the article
    - Returns the article_id (GUID)
    
    Args:
        cursor: Database cursor
        fk_case: Case ID
        event_id: Case event GUID to link
        event_date: Calendar date for article grouping
        story_headline: Article headline (optional)
        story_sub_head: Article subhead (optional)
        story_body: Article body text (optional)
        image_url: Featured image URL (optional)
        ai_model: AI model used (e.g., 'gemini-2.5-flash')
        ai_prompt: AI prompt text (optional)
        ai_tokens_input: Input tokens used
        ai_tokens_output: Output tokens generated
        ai_cost: API cost in dollars
        generated_by: Source identifier (default: 'pipeline')
    
    Returns:
        Article GUID as string, or None if error
    
    Example:
        article_id = upsert_article_for_event(
            cursor=cursor,
            fk_case=12345,
            event_id='abc-123-def',
            event_date=datetime.now().date(),
            story_headline='Breaking: Celebrity Court Filing',
            story_body='Full story text here...',
            ai_model='gemini-2.5-flash',
            ai_tokens_input=1000,
            ai_tokens_output=500,
            ai_cost=0.00123
        )
    """
    try:
        # Convert date to string format for SQL
        if isinstance(event_date, datetime):
            event_date = event_date.date()
        event_date_str = event_date.strftime('%Y-%m-%d')
        
        # Call stored procedure with OUTPUT parameter
        sql = """
        DECLARE @article_id UNIQUEIDENTIFIER
        
        EXEC dbo.upsert_article_for_event
            @fk_case = ?,
            @event_id = ?,
            @event_date = ?,
            @story_headline = ?,
            @story_sub_head = ?,
            @story_body = ?,
            @image_url = ?,
            @ai_model = ?,
            @ai_prompt = ?,
            @ai_tokens_input = ?,
            @ai_tokens_output = ?,
            @ai_cost = ?,
            @generated_by = ?,
            @article_id = @article_id OUTPUT
        
        SELECT @article_id AS article_id
        """
        
        cursor.execute(sql, (
            fk_case,
            event_id,
            event_date_str,
            story_headline,
            story_sub_head,
            story_body,
            image_url,
            ai_model,
            ai_prompt,
            ai_tokens_input,
            ai_tokens_output,
            ai_cost,
            generated_by
        ))
        
        result = cursor.fetchone()
        if result and result.article_id:
            article_id = str(result.article_id)
            logger.info(f"Upserted article {article_id} for case {fk_case}, event {event_id}")
            return article_id
        else:
            logger.warning(f"upsert_article_for_event returned NULL for case {fk_case}, event {event_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error upserting article for case {fk_case}, event {event_id}: {e}")
        raise


def get_todays_article(
    cursor,
    fk_case: int,
    article_date: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the current Pending article for a case on a given date.
    
    Args:
        cursor: Database cursor
        fk_case: Case ID
        article_date: Date to query (default: today)
    
    Returns:
        Dictionary with article data, or None if not found
        
    Example:
        article = get_todays_article(cursor, case_id=12345)
        if article:
            print(article['story_headline'])
            print(article['version'])
    """
    try:
        if article_date is None:
            article_date = date.today()
        elif isinstance(article_date, datetime):
            article_date = article_date.date()
        
        article_date_str = article_date.strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT TOP 1
                id,
                fk_case,
                article_date,
                articleStatus,
                story_headline,
                story_sub_head,
                story_body,
                image_url,
                version,
                created_at,
                updated_at,
                ai_model,
                ai_tokens_input,
                ai_tokens_output,
                ai_cost,
                generated_by,
                is_published,
                published_at
            FROM dbo.articles
            WHERE fk_case = ?
              AND article_date = ?
              AND articleStatus = 'Pending'
            ORDER BY created_at DESC
        """, (fk_case, article_date_str))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': str(row.id),
                'fk_case': row.fk_case,
                'article_date': row.article_date,
                'articleStatus': row.articleStatus,
                'story_headline': row.story_headline,
                'story_sub_head': row.story_sub_head,
                'story_body': row.story_body,
                'image_url': row.image_url,
                'version': row.version,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                'ai_model': row.ai_model,
                'ai_tokens_input': row.ai_tokens_input,
                'ai_tokens_output': row.ai_tokens_output,
                'ai_cost': row.ai_cost,
                'generated_by': row.generated_by,
                'is_published': row.is_published,
                'published_at': row.published_at
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting today's article for case {fk_case}, date {article_date}: {e}")
        raise


def get_article_by_id(cursor, article_id: str) -> Optional[Dict[str, Any]]:
    """
    Get article by ID.
    
    Args:
        cursor: Database cursor
        article_id: Article GUID
    
    Returns:
        Dictionary with article data, or None if not found
    """
    try:
        cursor.execute("""
            SELECT
                id,
                fk_case,
                article_date,
                articleStatus,
                story_headline,
                story_sub_head,
                story_body,
                image_url,
                version,
                created_at,
                updated_at,
                ai_model,
                ai_tokens_input,
                ai_tokens_output,
                ai_cost,
                generated_by,
                is_published,
                published_at,
                notes
            FROM dbo.articles
            WHERE id = ?
        """, (article_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': str(row.id),
                'fk_case': row.fk_case,
                'article_date': row.article_date,
                'articleStatus': row.articleStatus,
                'story_headline': row.story_headline,
                'story_sub_head': row.story_sub_head,
                'story_body': row.story_body,
                'image_url': row.image_url,
                'version': row.version,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                'ai_model': row.ai_model,
                'ai_tokens_input': row.ai_tokens_input,
                'ai_tokens_output': row.ai_tokens_output,
                'ai_cost': row.ai_cost,
                'generated_by': row.generated_by,
                'is_published': row.is_published,
                'published_at': row.published_at,
                'notes': row.notes
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        raise


def complete_article(
    cursor,
    article_id: str,
    username: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """
    Mark a Pending article as Completed.
    
    This "locks in" the article and allows new events to create a fresh Pending article.
    
    Args:
        cursor: Database cursor
        article_id: Article GUID to complete
        username: Username who completed it (optional)
        notes: Completion notes (optional)
    
    Returns:
        True if successful, False otherwise
    
    Example:
        success = complete_article(
            cursor=cursor,
            article_id='abc-123-def',
            username='editor1',
            notes='Story approved and published'
        )
    """
    try:
        cursor.execute("""
            EXEC dbo.complete_article
                @article_id = ?,
                @username = ?,
                @notes = ?
        """, (article_id, username, notes))
        
        # Fetch result set to confirm
        result = cursor.fetchone()
        if result:
            logger.info(f"Completed article {article_id}")
            return True
        else:
            logger.warning(f"complete_article returned no result for {article_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error completing article {article_id}: {e}")
        raise


def get_articles_for_case(
    cursor,
    fk_case: int,
    include_closed: bool = True,
    limit: int = 10
) -> list:
    """
    Get articles for a case, ordered by date descending.
    
    Args:
        cursor: Database cursor
        fk_case: Case ID
        include_closed: Include Closed articles (default: True)
        limit: Maximum number of articles to return
    
    Returns:
        List of article dictionaries
    
    Example:
        articles = get_articles_for_case(cursor, case_id=12345, limit=5)
        for article in articles:
            print(f"{article['article_date']}: {article['story_headline']}")
    """
    try:
        where_clause = ""
        if not include_closed:
            where_clause = "AND articleStatus IN ('Pending', 'Completed')"
        
        sql = f"""
            SELECT TOP {limit}
                id,
                article_date,
                articleStatus,
                story_headline,
                version,
                updated_at,
                is_published
            FROM dbo.articles
            WHERE fk_case = ?
            {where_clause}
            ORDER BY article_date DESC, version DESC
        """
        
        cursor.execute(sql, (fk_case,))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'id': str(row.id),
                'article_date': row.article_date,
                'articleStatus': row.articleStatus,
                'story_headline': row.story_headline,
                'version': row.version,
                'updated_at': row.updated_at,
                'is_published': row.is_published
            })
        
        return articles
        
    except Exception as e:
        logger.error(f"Error getting articles for case {fk_case}: {e}")
        raise


# Convenience function for backward compatibility
def save_article_from_summary(
    cursor,
    fk_case: int,
    event_id: str,
    event_date: date,
    parsed_summary: Dict[str, Any],
    ai_model: Optional[str] = None,
    ai_tokens_input: Optional[int] = None,
    ai_tokens_output: Optional[int] = None,
    ai_cost: Optional[float] = None
) -> Optional[str]:
    """
    Convenience wrapper for upserting article from parsed summary dict.
    
    This is designed to integrate with existing summary parser output.
    
    Args:
        cursor: Database cursor
        fk_case: Case ID
        event_id: Event GUID
        event_date: Event date
        parsed_summary: Dictionary with keys: story_headline, story_sub_head, story_body
        ai_model: AI model name
        ai_tokens_input: Input tokens
        ai_tokens_output: Output tokens
        ai_cost: API cost
    
    Returns:
        Article GUID as string
    """
    return upsert_article_for_event(
        cursor=cursor,
        fk_case=fk_case,
        event_id=event_id,
        event_date=event_date,
        story_headline=parsed_summary.get('story_headline'),
        story_sub_head=parsed_summary.get('story_sub_head'),
        story_body=parsed_summary.get('story_body'),
        ai_model=ai_model,
        ai_tokens_input=ai_tokens_input,
        ai_tokens_output=ai_tokens_output,
        ai_cost=ai_cost,
        generated_by='summary_parser'
    )
