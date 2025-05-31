from google import genai
from google.genai import types
import os
import dotenv
import json
from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from pydantic import BaseModel, Field
import asyncio
from textwrap import dedent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
dotenv.load_dotenv()

MODEL = "gemini-2.0-flash"
# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# class EmailResponse(BaseModel):
#     subject: str = Field(description="The subject of the email")
#     body: str = Field(description="The body of the email")

# class EmailVerifierResponse(BaseModel):
#     email_exists: bool = Field(description="Whether the email exists in the list")
#     email: str = Field(description="The email that is present in the content")
#     name: str = Field(description="The name that is present in the content")

class EmailTeamResponse(BaseModel):
    user_email: str = Field(description="The email of the user")
    user_name: str = Field(description="The name of the user")
    subject: str = Field(description="The subject of the email")
    body: str = Field(description="The body of the email")


# Factory function for Email Writer Agent
email_writer_agent = Agent(
        name="Email Writer",
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id=MODEL,
            grounding=False,
            system_prompt='''
            <Instructions>
            You are a copywriter agent for my email.
            You are my personal assistant and I trust your judgement.
            You need to write a pure copy of email without any placeholders or templates.
            You need to write a email that sounds like it is written by a human.
            Keep the tone of email to be business casual.
            Make sure that you are not repeating the same words or phrases.
            Don't use too many adjectives.
            Don't use very heavy english, keep it simple and natural.
            The 'body' field should contain only the main message of the email, without any redundant repetitions of the entire content.
            </Instructions>

            <SUPER IMPORTANT>
            - For the ending of the email, mention my name as "Aaditya from Jovian AI"
            - You MUST NOT use [YOUR NAME] or [MY NAME] in the email or any other placeholder.
            </SUPER IMPORTANT>
            ''',
            search=False
        ),
    )

# Factory function for Email Verifier Agent
email_verifier_agent = Agent(
        name="Email Verifier",
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id=MODEL,
            grounding=False,
            system_prompt='''
            <Instructions>
            You are a email verifier agent.
            You are my personal assistant and I trust your judgement.
            I have a list of emails and I want you to check 2 things:
            1. If there is any relevant email in the list.
            2. If email/name is there which email is it refering to.
            You must read the content and then check the list of emails to give the correct output.
            The content may not be perfect, names could be misspelled, emails could be misspelled.
            You must give the correct output.
            You must check if either the email is present in the content or the name is present in the content.
            return the email and the name.
            If neither are present, return empty string for both email and name.
            ''',
            instructions=dedent('''
            <IMPORTANT>
            - YOU ARE ONLY ALLOWED TO RETURN THE EMAIL AND NAME FROM THE LIST OF EMAILS.
            - DO NOT MAKE UP ANY PLACEHOLDERS EMAIL SUCH AS SAM@EXAMPLE.COM.
            - DO NOT MAKE UP ANY NAME IN THE LIST OF EMAILS.
            - DO NOT MAKE UP ANY EMAILS.
            - For the ending of the email, mention my name as "Aaditya from Jovian AI" completely not [MY NAME] or [YOUR NAME] or just "Aaditya", just "Aaditya from Jovian AI"
            - You MUST NOT use [YOUR NAME] or [MY NAME] in the email or any other placeholder.
            </IMPORTANT>
            </Instructions>
            
            <EMAILS>
            [
                {
                    "name": "Sam",
                    "email": "sam@gmail.com",
                }, {
                    "name": "Aaditya",
                    "email": "aadityajagdale.21@gmail.com", 
                }, {
                    "name": "John",
                    "email": "john@gmail.com",
                }
            ]
            </EMAILS>
            '''),
        ),
    )


email_assistant_team = Team(
    name="Email Assistant Team",
    mode="collaborate",
    model=Gemini(
        api_key=GEMINI_API_KEY,
        id=MODEL,
        grounding=False,
        generation_config={
            "tool_config": {
                "function_calling_config": {"mode": "NONE"}
            }
        }
    ),
    instructions=[
        'You are a email assistant team.',
        'You are my personal assistant and I trust your judgement.',
        'You have 2 tasks to complete:',
        '1. Verify if the email is present in the list of emails and return the correct email and name using the email_verifier_agent.',
        '2. If the email is present, write the email using the email_writer_agent.',
        'You must complete both the tasks to succeed.',
        'If you fail to complete either of the tasks, you will be penalized.',
        'You will be penalized by 10 points if you fail to complete either of the tasks.',
        """
        <IMPORTANT>
        - YOU ARE ONLY ALLOWED TO RETURN THE EMAIL AND NAME FROM THE LIST OF EMAILS.
        - DO NOT MAKE UP ANY PLACEHOLDERS EMAIL SUCH AS SAM@EXAMPLE.COM.
        - DO NOT MAKE UP ANY NAME SUCH AS SAM.
        - DO NOT MAKE UP ANY EMAILS.
        </IMPORTANT>
        </Instructions>
        
        <EMAILS>
        [
            {
                "name": "Sam",
                "email": "sam@gmail.com",
            }, {
                "name": "Aaditya",
                "email": "aadityajagdale.21@gmail.com", 
            }, {
                "name": "John",
                "email": "john@gmail.com",
            }
        ]
        </EMAILS>
            """
    ],
    success_criteria='Email is selected from the list of emails and the email content is written',
    response_model=EmailTeamResponse,    
    enable_agentic_context=True,
    show_tool_calls=True,
    markdown=True,
    show_members_responses=True,
    members=[
        email_verifier_agent,
        email_writer_agent,
    ],
)
