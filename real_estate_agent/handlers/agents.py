# install chromadb - `pip install chromadb`

import asyncio
import json
from agno.agent import Agent
from agno.team import Team
from agno.knowledge.json import JSONKnowledgeBase
from agno.vectordb.chroma import ChromaDb
from agno.embedder.ollama import OllamaEmbedder
from agno.models.google import Gemini
from agno.models.ollama import Ollama
from textwrap import dedent
from pydantic import BaseModel, Field
import os
import dotenv

dotenv.load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Your JSON data
ollama_embedder = OllamaEmbedder(id="nomic-embed-text:v1.5", dimensions=768)

# Initialize ChromaDB
properties_db = ChromaDb(
    collection="real_estate_agent_properties", 
    path="tmp/chromadb", 
    persistent_client=True, 
    embedder=ollama_embedder
)

meetings_db = ChromaDb(
    collection="real_estate_agent_meetings", 
    path="tmp/chromadb", 
    persistent_client=True, 
    embedder=ollama_embedder
)

# Create knowledge base from JSON data
properties_kb = JSONKnowledgeBase(
    path="real_estate_agent/kb/detailed.json",
    vector_db=properties_db,
)

meetings_kb = JSONKnowledgeBase(
    path="real_estate_agent/kb/meetings.json",
    vector_db=meetings_db,
)

class PropertyModel(BaseModel):
    id: int = Field(description="The id of the property")
    title: str = Field(description="The title of the property")
    location: str = Field(description="The location of the property")
    price_usd: int = Field(description="The price of the property in USD")
    area_sqft: int = Field(description="The area of the property in square feet")
    bedrooms: int = Field(description="The number of bedrooms in the property")
    bathrooms: int = Field(description="The number of bathrooms in the property")
    property_type: str = Field(description="The type of the property")
    image_url: str = Field(description="The image url of the property")

class MeetingModel(BaseModel):
    id: int = Field(description="The id of the meeting")
    available_at: str = Field(description="The available time of the meeting")
    agent_name: str = Field(description="The name of the agent")
    agent_phone: str = Field(description="The phone number of the agent")
    agent_email: str = Field(description="The email of the agent")
    agency: str = Field(description="The agency of the agent")
    status: str = Field(description="The status of the meeting")

class RealEstateAgentOutput(BaseModel):
    message: str = Field(description="The message to be sent to the user")
    properties: list[PropertyModel] | None = Field(description="The list of properties from properties_kb")
    meetings: list[MeetingModel] | None = Field(description="The list of meetings from meetings_kb")

def get_real_estate_agent(query: str) -> RealEstateAgentOutput:
    # Create and use the agent
    properties_agent = Agent(
        name="Real Estate Agent",
        description="A real estate agent that can help you find city specific properties of USA",
        # model=Gemini(api_key=GEMINI_API_KEY), 
        model=Ollama(id="llama3.2:3b"),
        knowledge=properties_kb, 
        show_tool_calls=True, 
        search_knowledge=True,
        add_references=True,
        add_history_to_messages=True,
        num_history_runs=20,
        read_chat_history=True,
        response_model=list[PropertyModel],
        system_message=dedent("""
            <goal>
            - Your ONLY goal is to answer all the questions about our real estate company and properties.
            - You MUST refuse to answer anything that is not related to our real estate company and properties.
            </goal>
            <rules>
            - You have to give general information about the properties in the city.
            - If the user intent looks very promising, you MUST ask them to book a call with us and we will assign a private assistant just for them.
            - For general information, you can use the search_knowledge tool to find properties in a city.
            - You should use knowledge base to get list of all the properties and its details.
            </rules>
            <using_knowledge>
            - You can use the search_knowledge tool to find properties in a city.
            - Your queries should be in key value pairs.
            - Whenever user asks to look for properties, hand pick the appropriate key from the message and use it to search the knowledge base.
            - All the available keys are:
                - "id"
                - "title"
                - "location"
                - "price_inr"
                - "area_sqft"
                - "bedrooms"
                - "bathrooms"
                - "property_type"
            - For example, if user asks to look for properties in Miami, your query should be: "location: Miami"
            - For example, if user asks to look for properties in Miami under 1 million, your query should be: "location: Miami, price_usd: 1000000"
            </using_knowledge>
            <context>
            - You are a real estate agent that can help you find city specific properties of USA.
            - Your name is Jasmine.
            - The company name is ABC international real estate.
            - The company is based in Miami, USA.
            - The company right now has 30 employess and exclusively sells uber luxury properties in USA.
            - The company has a team of 100+ real estate agents who are experts in their field.
            - The company was founded in 2000 by Mr. John Doe.
            - We are the most trusted real estate company in USA when it comes to uber luxury properties.
            - We also sell properties in other countries like USA, UK, Australia, etc.
            - But right now all the properties are sold out in all the countries except USA
            </context>
            <output>
            - The main output is the message.
            - The message is going to be displayed to the user.
            - You also have to attach the relevant properties to the message in the properties field.
            - ONLY ATTACH THE PROPERTIES THAT ARE RELEVANT TO THE USER'S QUESTIONS
            - DO NOT ATTACH PROPERTIES WHEN USER ASKS FOR GENERAL INFORMATION
            - The properties field is a list of PropertyModel objects.
            - The PropertyModel object has the following fields:
                - id: int
                - title: str
                - location: str
                - price_inr: int
                - area_sqft: int
                - bedrooms: int
                - bathrooms: int
                - property_type: str
                - image_url: str
            - The properties field should be a list of PropertyModel objects.
            - The properties field should be empty if user asks for general information.
            - The price in messages should be numbers below million. Above million, you should use the word "million" in the message.
            - The area in messages should be in Sqft, Sqm, etc.
            </output>
        """),
    )

    booking_agent = Agent(
        name="Booking Agent",
        description="A real estate agent that can help you book a call with us and we will assign a private assistant just for them.",
        model=Gemini(api_key=GEMINI_API_KEY), 
        # model=Ollama(id="llama3.2:3b"),
        knowledge=properties_kb, 
        show_tool_calls=True, 
        search_knowledge=True,
        add_references=True,
        add_history_to_messages=True,
        num_history_runs=20,
        read_chat_history=True,
        add_context=True,
        context={"meeting_link": "https://cal.com/aadi-jovian/30"},
        system_message=dedent("""
            <goal>
            - Your ONLY goal is to book a call with us and we will assign a private assistant just for them.
            </goal>
            <input>
            - Right now its a roleplay, so you are going to ask for user's name and phone number.
            - Then do a search_knowledge tool call to find all the available meetings for the user.
            - And just let them know which assistant is assigned to them based on the availability from the search_knowledge tool call.
            - Once they finalized on the agent send them this exact same link to book the call.
            - https://cal.com/aadi-jovian/30
            - DO NOT CHANGE TO LINK, THIS IS THE EXACT LINK TO BOOK THE CALL.
            </input>
            <knowledge>
            - Extract the user's name and phone number from the user's message.
            - Search for available slots for the user.
            - If the user is available, book the call and send them the link to book the call.
            - If the user is not available, send them the message that we are fully booked and our agent will call them soon as soon as they are available.
            </knowledge>
        """),
    )

    intern_team = Team(
        name="Intern Team",
        description="A team of interns that can help you find city specific properties of USA",
        model=Ollama(id="llama3.2:3b"),
        mode="coordinate",
        instructions =dedent("""
            <goal>
            - Your ONLY goal is to answer all the questions about our real estate company and properties.
            - You must understand the context and the requirement from user's query and notify a relevant agent to handle the query.
            </goal>
            <agents>
            - properties_agent: A real estate agent that can help you do a query to find all available properties
            - booking_agent: A real estate agent that can help you book a call with us and we will assign a private assistant just for them.
            <rules>
            - You have to give general information about the properties in the city.
            - If the user intent looks very promising, you MUST ask them to book a call with us and we will assign a private assistant just for them.
            - For general information, you can use the search_knowledge tool to find properties in a city.
            - You should use knowledge base to get list of all the properties and its details.
            </rules>
        """),
        enable_agentic_context=True,
        enable_team_history=True,
        members=[properties_agent, booking_agent],
        add_datetime_to_instructions=True,
        add_member_tools_to_system_message=False,
        share_member_interactions=True,
        show_members_responses=True,
        markdown=True,
        response_model=RealEstateAgentOutput,
        expected_output="A message to the user, IF needed Properties, IF needed Meeting details "
    )

    return booking_agent.print_response(query)


get_real_estate_agent("I would like to book a call with you. My name is John Doe and my phone number is 1234567890")
