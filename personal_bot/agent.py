from google import genai
from google.genai import types
import os
import dotenv
import json
from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from agno.tools import googlesearch
from pydantic import BaseModel, Field
from textwrap import dedent
from agno.knowledge import AgentKnowledge
from email_service.gemini_service import email_assistant_team, EmailTeamResponse

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
dotenv.load_dotenv()

MODEL = "gemini-2.0-flash"

company_info_agent = Agent(
    name="Company Info Agent",
    description="You are a company info agent. You have to answer the user's question about the company and its services.",
    model=Gemini(
        api_key=GEMINI_API_KEY,
        id=MODEL,
        grounding=True,
    ),
    tools=[
        googlesearch,
    ],
    role="You are a company info agent. You have to answer the user's question about the company and its services.",
    add_name_to_instructions=True,
    markdown=False,
    add_history_to_messages=True,
    read_chat_history=True,
    goal="Seduce the user into booking a slot for a free consultation with us",
    system_message=dedent("""
        <|iam_goal_start|>
        Your PRIMARY goal is to seduce the user into booking a slot for a free consultation with us.
        Your SECONDARY goal is to provide information about the company and its services.
        </|iam_goal_end|>
        <|iam_instructions_start|>
        Users will ask you some questions.
        You MUST talk like a human, not like a robot.
        The answers must be short and concise.
        You can NEVER use markdown in your response.
        You can NEVER use bold in your response.
        You MUST refuse to answer any question that is not related to my company and its services.
        </|iam_instructions_end|>
        """),
    context={
        "company_info" : {
            "name" : "Jovian AI",
            "description" : "We build AI agents & AI systems for growing businesses.",
            "capability" : "We provide custom AI solutions to EVERY problem in your business.",
            "availability" : "We are completely booked for next 2 weeks and will not be able to take on any new projects. But if you want to book a slot you MUST book it RIGHT NOW otherwise we might run out of slots again.",
            "time_to_complete_a_project" : "One project takes on an average of 1-2 weeks to complete.",
            "pricing" : "There is no fixed price for a project. It depends on the complexity of the project.",
            "contact" : "To get started you can send your email or phone number in the chat and we will get back to you.",
        },
        "process" : {
            "1" : "The user can instantly book a slot for a free consultation with us.",
            "2" : "In that call, we'll analyze their business, their problems, and their goals.",
            "3" : "We'll then provide them with a proper document that will inform them all the ways they can use AI to solve their problems.",
            "4" : "If they are interested in any of the solutions, we can book them in the immediate next available slot.",
        },
    },
    instructions=[
        "Always be friendly and professional.",
        "Try to keep the conversation business casual",
        "Answer should be short and concise.",
        "You must answer on point without too much fluff.", 
        "For every dead end question, you must ask another question to get the conversation flowing.",
        "You can ask if they want to book a slot, get a free consultation, or if they have any questions about the company.",
    ],
)

def just_chat_with_company_info_agent(user_request: str, history: list[dict] = None) -> str:
    return company_info_agent.run(user_request).content



def personal_assistant_team(user_request: str, history: list[dict] = None) -> EmailTeamResponse | str:
    team = Team(
        name="Personal Assistant Team",
        mode="route",
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id=MODEL,
            grounding=False,
        ),
        members=[
            email_assistant_team,
            company_info_agent
        ],
        enable_team_history=True,
        enable_user_memories=True,
        context={
            'chat_history': history,
        },
        instructions=[
            "You are my company's personal assistant.",
            "The user will be asking you a question.",
            "You have to decide what kind of request is user making and route it to the correct agent.",
            "Here are the agents you have:",
            "1. Email Assistant: This agent is responsible for sending emails.",
            "2. Company Info Agent: This agent is responsible for answering questions about the company and its services.",
            "You have to stop the discussion when you think the team has reached a consensus.",
            "Whenever someone gives a greeting message, you must say this: 'Hello! I'm Jovian from Jovian AI. We build AI agents & AI systems for growing businesses. How can I help you today?'",
        ],
        success_criteria="The team has reached a consensus.",
        expected_output="The request has been handled by the correct agent.",
        enable_agentic_context=True,
        show_tool_calls=False,
        markdown=False,
        show_members_responses=False,
    )
    return team.run(user_request).content

async def get_summary_from_agno(data: object) -> str:
    summary_agent = Agent(
        name="Summary Agent",
        description="You are a summary agent. You have to summarize the data provided to you.",
        role="You are a summary agent. You have to summarize the data provided to you.",
        goal="Summarize the data such that you can maximize value per word used.",
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id=MODEL,
            grounding=False,
        ),
        context=data,
        add_context=True,
        system_message=dedent("""
            <|iam_goal_start|>
            Your ONLY goal is to summarize the data provided to you.
            </|iam_goal_end|>
            <|iam_instructions_start|>
            - You have to summarize the data provided to you that gives out some valueable content.
            - Take comments into consideration to sum up what people are saying about the post.
            </|iam_instructions_end|>
            <|iam_reward_start|>
            You will be evaluated on the quality of the summary.
            You will maximize value per word provided.
            Higher value per word will be rewarded.
            </|iam_reward_end|>
        """),
        instructions=[
            "You have to summarize the data provided to you that gives out some valueable content.",
            "Talk like a human, not like a robot.",
            "Just simply summarize the data provided to you.",
        ],
    )
    return summary_agent.run('Give me a summary of the data provided to you').content

def linkedin_post_generator(data: object) -> str:
    linkedin_post_generator_agent = Agent(
        name="LinkedIn Post Generator Agent",
        description="You are a LinkedIn post generator agent. You have to generate a LinkedIn post based on the data provided to you.",
        role="You are a LinkedIn post generator agent. You have to generate a LinkedIn post based on the data provided to you.",
        goal="Generate a LinkedIn post based on the data provided to you",

        model=Gemini(
            api_key=GEMINI_API_KEY,
            id=MODEL,
            grounding=False,
        ),
        context=data,
        add_context=True,
        tools=[
            googlesearch
        ],
        system_message=dedent("""
            <|iam_goal_start|>
            Your ONLY goal is to generate a LinkedIn post based on the data provided to you.
            </|iam_goal_end|>
            <|iam_instructions_start|>
            - You run an AI automation agency, and this is your way of marketing your services.
            - You cannot make it super obvious but you have to be smart with the content
            - So all the content that you generate should be aligned with the company's values and goals.
            - You MUST generate a very engaging hook for the post.
            - The body will be the text that comes after the hook. Hence, dont repeat the hook in the body.
            - The target audience for the post is AI enthusiasts and Entrepreneurs who are looking to grow their business using AI.
            - The post should be short and concise.
            - The post should be engaging and interesting.
            - The post should be SEO friendly.
            - The post should be in the format of a LinkedIn post.
            - Use emojis to make the post more engaging.
            - Use bullet points to deliver maximum value with less words.
            </|iam_instructions_end|>
            <|iam_output_start|>
            You have to ONLY generate a LinkedIn post based on the data in a way that is easy to understand. Do not add anything else to the output. You will be evaluated on the quality of the post.
            </|iam_output_end|>
        """),
        instructions=[
            "You have to generate a LinkedIn post based on the data in a way that is easy to understand.",
            "Make sure you add a lot of value to this post instead of just repeating the data.",
            "If the body text has some URL, you HAVE to use google search tool to get the data from the URL to get more context about the contents of the post",
            "You have to use the tools provided to you to get the data.",
            "You have to use the tools provided to you to generate the post.",
            "The post needs to be short and concise.",
            "Use bullet points to make the post more engaging.",
        ],
    )
    return linkedin_post_generator_agent.run('Give me a LinkedIn post based on the data provided to you').content