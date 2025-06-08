# install chromadb - `pip install chromadb`

import asyncio
import json
from agno.agent import Agent
from agno.knowledge.json import JSONKnowledgeBase
from agno.vectordb.chroma import ChromaDb
from agno.embedder.ollama import OllamaEmbedder
from agno.models.google import Gemini
from textwrap import dedent
from pydantic import BaseModel, Field
import os
import dotenv

dotenv.load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Your JSON data
ollama_embedder = OllamaEmbedder(id="nomic-embed-text:v1.5", dimensions=768)

# Initialize ChromaDB
vector_db = ChromaDb(
    collection="real_estate_agent", 
    path="tmp/chromadb", 
    persistent_client=True, 
    embedder=ollama_embedder
)

# Create knowledge base from JSON data
knowledge_base = JSONKnowledgeBase(
    path="real_estate_agent/kb/general.json",
    vector_db=vector_db,
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

class RealEstateAgentOutput(BaseModel):
    message: str = Field(description="The message to be sent to the user")
    properties: list[PropertyModel] | None = Field(description="The list of properties to be sent to the user")

def get_real_estate_agent(query: str) -> RealEstateAgentOutput:
    # Create and use the agent
    real_estate_agent = Agent(
        name="Real Estate Agent",
        description="A real estate agent that can help you find city specific properties of USA",
        model=Gemini(api_key=GEMINI_API_KEY), 
        knowledge=knowledge_base, 
        show_tool_calls=True, 
        search_knowledge=True,
        add_references=True,
        add_history_to_messages=True,
        num_history_runs=20,
        read_chat_history=True,
        use_json_mode=True,
        response_model=RealEstateAgentOutput,
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
    return real_estate_agent.run(query).content
