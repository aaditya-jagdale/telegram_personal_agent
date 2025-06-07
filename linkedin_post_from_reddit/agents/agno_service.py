from agno.agent import Agent
from textwrap import dedent
from agno.models.google import Gemini
import os
import dotenv
import asyncio
import logging

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash-preview-05-20"

async def get_summary_from_agno(data: dict) -> str:
    try:
        if not data:
            logger.error("No data provided to get_summary_from_agno")
            return "Error: No data provided for summarization"

        # Validate required fields
        required_fields = ['title', 'body', 'comments']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return f"Error: Missing required fields: {', '.join(missing_fields)}"

        summary_agent = Agent(
            name="summary_agent",
            description="You are a helpful assistant that summarizes reddit posts",
            goal="Generate a precise and concise summary of 1. reddit post and 2. comments on the post",
            add_context=True,
            context=data,
            model=Gemini(
                api_key=GEMINI_API_KEY,
                id=MODEL,
                grounding=True,  # Enable grounding for better context understanding
            ),
            system_message=dedent(
                """
                <persona>
                - You are an expert copywriter specializing in creating clear, engaging summaries
                - Your goal is to deliver maximum value with minimum words
                - You excel at distilling complex information into easily digestible content
                - You maintain a professional yet accessible tone
                </persona>

                <instructions>
                - Analyze the post title, body, and comments thoroughly
                - Create a concise summary that captures the main points and key discussions
                - Use simple, clear language that anyone can understand
                - Focus on the most valuable insights and takeaways
                - Structure the summary in a logical flow
                - Include relevant context from comments if they add value
                </instructions>

                <constraints>
                - Keep the summary under 200 words
                - Avoid technical jargon unless absolutely necessary
                - Don't include redundant information
                - Don't make assumptions beyond what's in the provided content
                - Don't include personal opinions or biases
                </constraints>

                <output_format>
                The summary should be structured as follows:
                1. Main topic/theme (1-2 sentences)
                2. Key points from the post (2-3 bullet points)
                3. Notable insights from comments (1-2 bullet points)
                4. Overall takeaway (1 sentence)
                </output_format>
                """
            )
        )
        
        response = summary_agent.run("Summarize the post")
        if not response or not hasattr(response, 'content'):
            logger.error("Summary generation failed - invalid response")
            return "Error: Failed to generate summary"
            
        summary_content = response.content
        if not summary_content:
            logger.error("Summary generation failed - empty content")
            return "Error: Failed to generate summary"
            
        return str(summary_content)  # Ensure we return a string

    except Exception as e:
        logger.error(f"Error in get_summary_from_agno: {str(e)}")
        return f"Error: Failed to generate summary - {str(e)}"

def linkedin_post_generator(data: dict) -> str:
    try:
        if not data:
            logger.error("No data provided to linkedin_post_generator")
            return "Error: No data provided for LinkedIn post generation"

        # Validate required fields
        required_fields = ['title', 'body', 'summary', 'original_post_url']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return f"Error: Missing required fields: {', '.join(missing_fields)}"

        linkedin_agent = Agent(
            name="linkedin_post_agent",
            description="You are an expert LinkedIn content creator",
            goal="Generate an engaging and professional LinkedIn post from Reddit content",
            add_context=True,
            context=data,
            model=Gemini(
                api_key=GEMINI_API_KEY,
                id=MODEL,
                grounding=True,
            ),
            system_message=dedent(
                """
                <persona>
                - You are an expert LinkedIn content creator specializing in AI and technology
                - You excel at creating engaging, professional, and thought-provoking content
                - You understand how to maximize engagement while maintaining professionalism
                - You know how to adapt Reddit content for a professional LinkedIn audience
                </persona>

                <instructions>
                - Create a LinkedIn post that's engaging and professional
                - Use the provided summary as a base but enhance it for LinkedIn
                - Include relevant hashtags for better visibility
                - Add a call-to-action to encourage engagement
                - Maintain a professional yet conversational tone
                - Structure the post for maximum readability
                </instructions>

                <constraints>
                - Keep the post under 300 words
                - Use 3-5 relevant hashtags
                - Include emojis strategically (2-3 per post)
                - Don't use Reddit-specific language or references
                - Don't include personal opinions or biases
                - Don't use overly technical jargon
                - Don't include the original Reddit URL directly
                </constraints>

                <output_format>
                The LinkedIn post should be structured as follows:
                1. Hook (1-2 sentences that grab attention)
                2. Main content (2-3 paragraphs)
                3. Key takeaways (2-3 bullet points)
                4. Call-to-action (1 sentence)
                5. Hashtags (3-5 relevant hashtags)
                </output_format>
                """
            )
        )

        response = linkedin_agent.run("Generate a LinkedIn post")
        if not response or not hasattr(response, 'content'):
            logger.error("LinkedIn post generation failed - invalid response")
            return "Error: Failed to generate LinkedIn post"
            
        post_content = response.content
        if not post_content:
            logger.error("LinkedIn post generation failed - empty content")
            return "Error: Failed to generate LinkedIn post"
            
        return str(post_content)  # Ensure we return a string

    except Exception as e:
        logger.error(f"Error in linkedin_post_generator: {str(e)}")
        return f"Error: Failed to generate LinkedIn post - {str(e)}"
    
def get_relevant_subreddits(description: str) -> list:
    try:
        if not description:
            logger.error("No description provided to get_relevant_subreddits")
            return []

        subreddit_agent = Agent(
            name="subreddit_agent",
            description="You are an expert at finding relevant subreddits",
            goal="Generate a list of relevant subreddits based on the provided description",
            add_context=True,
            context={"description": description},
            model=Gemini(
                api_key=GEMINI_API_KEY,
                id=MODEL,
                grounding=True,
            ),
            system_message=dedent(
                """
                <persona>
                - You are an expert at understanding Reddit's community structure
                - You excel at matching content themes with appropriate subreddits
                - You understand both popular and niche subreddit communities
                - You can identify both direct and related subreddits
                </persona>

                <instructions>
                - Analyze the provided description thoroughly
                - Identify key themes, topics, and interests
                - Suggest both popular and niche subreddits
                - Consider both direct matches and related communities
                - Prioritize active and well-moderated subreddits
                </instructions>

                <constraints>
                - Return 15-20 most relevant subreddits
                - Include a mix of popular and niche communities
                - Don't suggest NSFW subreddits unless explicitly relevant
                - Don't suggest inactive or poorly moderated subreddits
                - Don't include subreddits that don't allow self-promotion
                </constraints>

                <output_format>
                Return a list of subreddits in the following format:
                - Each subreddit should be prefixed with "r/"
                - One subreddit per line
                - No additional text or formatting
                - Dont add any context or explanation, just the list of subreddits
                </output_format>
                """
            )
        )
        
        response = subreddit_agent.run("Suggest relevant subreddits")
        if not response or not hasattr(response, 'content'):
            logger.error("Subreddit suggestion failed - invalid response")
            return []
            
        subreddits_content = response.content
        if not subreddits_content:
            logger.error("Subreddit suggestion failed - empty content")
            return []
            
        # Convert the response into a list of subreddits
        subreddits = [sub.strip() for sub in str(subreddits_content).split('\n') if sub.strip()]
        return subreddits

    except Exception as e:
        logger.error(f"Error in get_relevant_subreddits: {str(e)}")
        return []


