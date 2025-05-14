from google import genai
from google.genai import types
import os
import dotenv
import json

dotenv.load_dotenv()

MODEL = "gemini-2.0-flash-lite"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def gemini_email_writer(prompt):
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="""
            <Instructions>
            You are a copywriter agent for my email.
            You are my personal assistant and I trust your judgement.
            You need to write a pure copy of email without any placeholders or templates.
            You need to write a email that sounds like it is written by a human.
            Keep the tone of email to be business casual.
            Keep the email short and to the point.
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
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
            type = genai.types.Type.OBJECT,
            required = ["subject", "body"],
            properties = {
                "subject": genai.types.Schema(
                    type = genai.types.Type.STRING,
                ),
                "body": genai.types.Schema(
                    type = genai.types.Type.STRING,
                ),
            },
        ),
        ),
    )
    response_json = json.loads(response.text)
    return {
        "subject": response_json["subject"],
        "body": response_json["body"],
    }

def email_verifier(content: str, emails: list[dict]) -> dict:
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Content: {content}\nEmails: {emails}",
        config=types.GenerateContentConfig(
            system_instruction="""
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
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
            type = genai.types.Type.OBJECT,
            required = ["email_exists", "email"],
            properties = {
                "email_exists": genai.types.Schema(
                    type = genai.types.Type.BOOLEAN,
                ),
                "email": genai.types.Schema(
                    type = genai.types.Type.OBJECT,
                    properties = {
                        "name": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                        "email": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                    },
                ),
            },
        ),
        ),
    )
    response_json = json.loads(response.text)
    return response_json
