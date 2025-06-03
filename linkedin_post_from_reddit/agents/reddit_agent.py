import os
import random
import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def extract_media_url(post_data: dict) -> Optional[str]:
    """
    Extract media URL from a Reddit post.
    Handles images, videos, and galleries.
    
    Args:
        post_data (dict): The post data from Reddit API
        
    Returns:
        Optional[str]: The media URL if found, None otherwise
    """
    # Check for video content
    if post_data.get('is_video', False):
        if 'secure_media' in post_data and post_data['secure_media']:
            if 'reddit_video' in post_data['secure_media']:
                return post_data['secure_media']['reddit_video']['fallback_url']
    
    # Check for image content
    if 'url' in post_data:
        url = post_data['url']
        # Check if the URL is an image
        if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return url
    
    # Check for gallery content
    if 'gallery_data' in post_data:
        # For galleries, we'll return the first image
        if 'items' in post_data['gallery_data']:
            for item in post_data['gallery_data']['items']:
                if 'media_id' in item:
                    media_id = item['media_id']
                    if 'media_metadata' in post_data:
                        if media_id in post_data['media_metadata']:
                            metadata = post_data['media_metadata'][media_id]
                            if 's' in metadata and 'u' in metadata['s']:
                                return metadata['s']['u']
    
    return None

def get_random_hot_post_direct_api(
        subreddit_names: list,
        posts_limit_per_subreddit: int,
        min_score: int
) -> dict:
    """
    Fetches a random hot post from the specified subreddits that meets the minimum score requirement.
    
    Args:
        subreddit_names (list): List of subreddit names to search in
        posts_limit_per_subreddit (int): Number of posts to fetch from each subreddit
        min_score (int): Minimum score required for a post to be considered
        
    Returns:
        dict: Post data including title, body, score, URL, etc.
    """
    # Randomly select one subreddit from the list
    selected_subreddit = random.choice(subreddit_names)
    
    # Construct the Reddit API URL for hot posts
    url = f"https://www.reddit.com/r/{selected_subreddit}/hot.json?limit={posts_limit_per_subreddit}"
    
    # Set up headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Make the request to Reddit API
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the JSON response
        data = response.json()
        posts = data['data']['children']
        
        # Filter posts by minimum score
        valid_posts = [post['data'] for post in posts if post['data']['score'] >= min_score]
        
        if not valid_posts:
            logger.warning(f"No posts found in r/{selected_subreddit} with score >= {min_score}")
            return {}
        
        # Select a random post from the valid posts
        selected_post = random.choice(valid_posts)
        
        # Extract media URL
        media_url = extract_media_url(selected_post)
        
        # Construct the post data
        post_data = {
            'id': selected_post['id'],
            'title': selected_post['title'],
            'selftext': selected_post['selftext'],
            'subreddit': selected_post['subreddit'],
            'score': selected_post['score'],
            'num_comments': selected_post['num_comments'],
            'source_url': f"https://www.reddit.com{selected_post['permalink']}",
            'extracted_media_url': media_url,
            'is_video': selected_post.get('is_video', False)
        }
        
        return post_data
        
    except requests.RequestException as e:
        logger.error(f"Error fetching posts from r/{selected_subreddit}: {str(e)}")
        return {}
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing response from r/{selected_subreddit}: {str(e)}")
        return {}

def get_post_comments(subreddit: str, post_id: str, limit: int = 20) -> list:
    """
    Fetches comments for a specific post.
    
    Args:
        subreddit (str): Name of the subreddit
        post_id (str): ID of the post
        limit (int): Maximum number of comments to fetch
        
    Returns:
        list: List of comment texts
    """
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit={limit}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        comments = []
        
        # Extract comments from the response
        if len(data) > 1 and 'data' in data[1] and 'children' in data[1]['data']:
            for comment in data[1]['data']['children']:
                if 'data' in comment and 'body' in comment['data']:
                    comments.append(comment['data']['body'])
        
        return comments
        
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.error(f"Error fetching comments for post {post_id} in r/{subreddit}: {str(e)}")
        return []
