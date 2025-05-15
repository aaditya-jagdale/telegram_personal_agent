from google import genai
from google.genai import types
import os
import dotenv
import json
from agno.agent import Agent
from agno.models.google import Gemini
from pydantic import BaseModel, Field

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
dotenv.load_dotenv()

MODEL = "gemini-2.5-pro-preview-05-06"
# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class EmailResponse(BaseModel):
    subject: str = Field(description="The subject of the email")
    body: str = Field(description="The body of the email")

class EmailVerifierResponse(BaseModel):
    email_exists: bool = Field(description="Whether the email exists in the list")
    email: str = Field(description="The email that is present in the content")
    name: str = Field(description="The name that is present in the content")

def gemini_email_writer(prompt: str) -> EmailResponse | None:
    email_builder_agent = Agent(
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id="gemini-2.0-flash",
            grounding=False,
            system_prompt="""
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
            """,
            search=False
        ),
        structured_outputs=True,
        use_json_mode=True,
        response_model=EmailResponse,
    )
    response = email_builder_agent.run(prompt)
    return response.content

def email_verifier(content: str, emails: list[dict]) -> EmailVerifierResponse | None:
    email_verifier_agent = Agent(
        model=Gemini(
            api_key=GEMINI_API_KEY,
            id="gemini-2.0-flash",
            grounding=False,
            system_prompt="""
            You are a email verifier agent.
            You are my personal assistant and I trust your judgement.
            I have a list of emails and I want you to check 2 things:
            1. If there is any relevant email in the list.
            2. If email/name is there which email is it refering to.
            You must read the content and then check the list of emails to give the correct output.
            The content may not be perfect, names could be misspelled, emails could be misspelled.
            You must give the correct output.
            The emails will be in format {name: "name", email: "email"}
            The content will be a string.
            You must check if either the email is present in the content or the name is present in the content.
            If the email is present, return the email and the name.
            If the name is present, return the email and the name.
            If both are present, return the email and the name.
            If neither are present, return false.
            """,
        ),
        structured_outputs=True,
        use_json_mode=True,
        response_model=EmailVerifierResponse,
    )
    response = email_verifier_agent.run(f"Content: {content}\nEmails: {emails}")
    return response.content
