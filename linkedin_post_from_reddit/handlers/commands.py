import logging
from telegram import Update
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown
from telegram.error import BadRequest
from social.reddit import get_random_hot_post_direct_api, get_post_comments
from agent import get_summary_from_agno, linkedin_post_generator

# Global variable to store the last fetched Reddit post data
stored_reddit_post_data = None
logger = logging.getLogger(__name__)

async def linkedin_command(update: Update, context: CallbackContext, content: object = None) -> None:
    global stored_reddit_post_data
    if stored_reddit_post_data:
        title = stored_reddit_post_data.get('title', "N/A")
        body = stored_reddit_post_data.get('selftext', "")
        original_post_url = stored_reddit_post_data.get('url', "#")
        fetched_comments = stored_reddit_post_data.get('fetched_comments_texts', [])
        media_url = stored_reddit_post_data.get('extracted_media_url')

        comments_to_summarize_str = "\n\n".join(fetched_comments[:20])
        
        summary_from_agno : str = await get_summary_from_agno({
            "title": title,
            "body": body,
            "comments": comments_to_summarize_str,
            "original_post_url": original_post_url,
            "media_url": media_url,
        })

        linkedin_post_text : str = linkedin_post_generator({
                "title": title,
                "body": body,
                "summary": summary_from_agno,
                "original_post_url": original_post_url,
                "media_url": media_url,
            })

        if media_url:
            try:
                logger.info(f"LinkedIn command: Attempting to send photo {media_url} with generated text as caption.")
                await update.message.reply_photo(photo=media_url, caption=linkedin_post_text)
                logger.info(f"LinkedIn command: Successfully sent photo with caption.")
            except BadRequest as e_photo_caption:
                logger.warning(f"LinkedIn command: Failed to send photo {media_url} with caption (e.g. caption too long or bad URL): {e_photo_caption}. Sending text only.")
                await update.message.reply_text(linkedin_post_text)
            except Exception as e:
                logger.error(f"LinkedIn command: An unexpected error occurred while trying to send photo {media_url}: {e}. Sending text only.")
                await update.message.reply_text(linkedin_post_text)
        else:
            logger.info("LinkedIn command: No media_url found in stored Reddit data. Sending text only.")
            await update.message.reply_text(linkedin_post_text)
    else:
        await update.message.reply_text("No Reddit post has been fetched yet. Use the /reddit command first.")
    
async def summary_command(update: Update, context: CallbackContext) -> None:
    global stored_reddit_post_data
    if stored_reddit_post_data:
        title = stored_reddit_post_data.get('title', "N/A")
        body = stored_reddit_post_data.get('selftext', "")
        original_post_url = stored_reddit_post_data.get('url', "#")
        fetched_comments = stored_reddit_post_data.get('fetched_comments_texts', [])
        media_url = stored_reddit_post_data.get('extracted_media_url')
        
        comments_to_summarize_str = "\n\n".join(fetched_comments[:20])
        
        summary_from_agno : str = await get_summary_from_agno({
            "title": title,
            "body": body,
            "comments": comments_to_summarize_str,
            "original_post_url": original_post_url,
            "media_url": media_url,
        })
        
        await update.message.reply_text(summary_from_agno)
    else:
        await update.message.reply_text("No Reddit post has been fetched yet. Use the /reddit command first.")

async def reddit_command(update: Update, context: CallbackContext) -> None:
    global stored_reddit_post_data
    ai_focused_subreddits = [
        "artificial", "singularity", "MachineLearning", "LocalLLaMA",
        "OpenAI", "StableDiffusion", "AGI", "datascience", "computervision"
    ]
    desired_min_score = 50
    max_comments_to_fetch = 20

    random_ai_post_data = get_random_hot_post_direct_api(
        subreddit_names=ai_focused_subreddits,
        posts_limit_per_subreddit=20,
        min_score=desired_min_score
    )

    if random_ai_post_data:
        post_id = random_ai_post_data.get('id')
        subreddit_name = random_ai_post_data.get('subreddit')
        
        comments_texts = []
        if post_id and subreddit_name:
            comments_texts = get_post_comments(subreddit=subreddit_name, post_id=post_id, limit=max_comments_to_fetch)
        
        stored_reddit_post_data = random_ai_post_data
        stored_reddit_post_data['fetched_comments_texts'] = comments_texts

        title_raw = random_ai_post_data.get('title')
        body_raw = random_ai_post_data.get('selftext')
        subreddit_raw = random_ai_post_data.get('subreddit', 'unknown')
        score = random_ai_post_data.get('score', 0)
        reddit_post_url = random_ai_post_data.get('source_url')
        num_comments_on_post = random_ai_post_data.get('num_comments', 0)
        media_url_from_post = random_ai_post_data.get('extracted_media_url')

        title_raw_str = title_raw if title_raw is not None else 'No Title'
        body_raw_str = body_raw if body_raw is not None else ''
        media_url_display_raw_str = media_url_from_post if media_url_from_post is not None else 'N/A'

        # Prepare base message components
        subreddit_display_text_unescaped = f"r/{subreddit_raw}"
        base_info_unescaped = f"Found a post from {subreddit_display_text_unescaped} (Score: {score}, Comments on post: {num_comments_on_post}):"

        # Handle original post link for both plain text and markdown
        if reddit_post_url:
            original_post_link_unescaped = f"Original Post: {reddit_post_url}"
            # For Markdown, the URL in [text](URL) should generally be the raw URL.
            # Telegram's MarkdownV2 parser handles standard URL characters.
            original_post_link_markdown = f"🔗[{escape_markdown('Original Post', version=2)}]({reddit_post_url})"
        else:
            original_post_link_unescaped = "Original Post: Not available"
            original_post_link_markdown = escape_markdown("Original Post: Not available", version=2)

        # MarkdownV2 escaped components
        title_escaped = escape_markdown(title_raw_str, version=2)
        body_escaped = escape_markdown(body_raw_str, version=2) if body_raw_str else "No additional text content\\."
        subreddit_link_escaped = f"[{escape_markdown(subreddit_display_text_unescaped, version=2)}](https://www.reddit.com/r/{subreddit_raw})"
        base_info_escaped = f"Found a post from {subreddit_link_escaped} \\(Score: {score}, Comments on post: {num_comments_on_post}\\)\\:"
        media_link_text_escaped = escape_markdown("Media link", version=2)
        media_url_display_escaped = escape_markdown(media_url_display_raw_str, version=2)

        plain_text_message = f"""{base_info_unescaped}

{title_raw_str}
{body_raw_str if body_raw_str else "No additional text content."}

{original_post_link_unescaped}"""
        
        markdown_caption = f"""{base_info_escaped}

{title_escaped}
{body_escaped}

{original_post_link_markdown}"""
        
        markdown_message_text_only = f"""{base_info_escaped}

{title_escaped}
{body_escaped}

Media link\\: {media_url_display_escaped}
{original_post_link_markdown}"""

        if media_url_from_post:
            try:
                logger.info(f"Attempting to send photo with MarkdownV2 caption for post {post_id}")
                await update.message.reply_photo(photo=media_url_from_post, caption=markdown_caption, parse_mode="MarkdownV2")
                logger.info(f"Successfully sent photo with MarkdownV2 caption for post {post_id}")
            except BadRequest as e_markdown:
                logger.warning(f"Failed to send photo with MarkdownV2 caption for post {post_id}: {e_markdown}. Trying plain text caption.")
                plain_caption = f"""{base_info_unescaped}

{title_raw_str}
{body_raw_str if body_raw_str else "No additional text content."}

{original_post_link_unescaped}"""
                try:
                    await update.message.reply_photo(photo=media_url_from_post, caption=plain_caption)
                    logger.info(f"Successfully sent photo with plain text caption for post {post_id}")
                except BadRequest as e_plain_photo:
                    logger.error(f"Failed to send photo with plain text caption for post {post_id}: {e_plain_photo}. Falling back to text message.")
                    # Fallback to sending a text message with media link if photo fails
                    try:
                        await update.message.reply_text(markdown_message_text_only, parse_mode="MarkdownV2")
                        logger.info(f"Successfully sent text message (MarkdownV2) with media link for post {post_id}")
                    except BadRequest as e_text_markdown:
                        logger.warning(f"Failed to send text message with MarkdownV2 for post {post_id}: {e_text_markdown}. Trying plain text.")
                        final_fallback_text = f"""{plain_text_message}

Media link: {media_url_from_post}""" # Add media link to plain text
                        await update.message.reply_text(final_fallback_text)
                        logger.info(f"Successfully sent text message (plain) with media link for post {post_id}")
        else: # No media_url_from_post
            logger.info(f"No media found for post {post_id}. Sending text-only message.")
            try:
                # Use markdown_message_text_only as it includes "Media link: N/A" appropriately
                await update.message.reply_text(markdown_message_text_only, parse_mode="MarkdownV2")
                logger.info(f"Successfully sent text-only message (MarkdownV2) for post {post_id}")
            except BadRequest as e_text_markdown:
                logger.warning(f"Failed to send text-only message with MarkdownV2 for post {post_id}: {e_text_markdown}. Trying plain text.")
                # Use plain_text_message and add "Media link: N/A"
                final_plain_text = f"""{plain_text_message}

Media link: N/A"""
                await update.message.reply_text(final_plain_text)
                logger.info(f"Successfully sent text-only message (plain) for post {post_id}")

    else:
        await update.message.reply_text(
            "Sorry, I couldn't find any relevant AI posts matching the criteria right now. "
            "Try again later or adjust the subreddits/filters."
        )
