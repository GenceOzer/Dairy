import datetime
import os
import re
from typing import List, Optional

import dotenv
from fastapi import FastAPI, HTTPException
from langchain.chains import LLMChain
from langchain.chat_models import ChatAnthropic
from langchain.prompts import PromptTemplate
from loguru import logger
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .prompts import context_prompt_text_combo, initial_encouragement_prompt_text

dotenv.load_dotenv()

anthropic_chat_llm = ChatAnthropic(
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    anthropic_api_url=os.getenv("ANTHROPIC_API_BASE"),
)

app = FastAPI()


class JournalEntry(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    date: str = Field(sa_column_kwargs={"unique": True})
    text: str
    analysis_text: Optional[str]


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)

# Create the table
SQLModel.metadata.create_all(engine)


initial_encouragement_prompt = PromptTemplate(
    input_variables=["entry"], template=initial_encouragement_prompt_text
)

base_chain = LLMChain(
    llm=anthropic_chat_llm,
    prompt=initial_encouragement_prompt,
    llm_kwargs={"max_tokens_to_sample": 250},
)


@app.get("/api/all_entries/", response_model=List[JournalEntry])
def list_all_entries():
    with Session(engine) as session:
        entries = session.exec(select(JournalEntry)).all()
        return entries


@app.get("/api/entries/", response_model=List[str])
def list_entries():
    with Session(engine) as session:
        entries = session.exec(select(JournalEntry)).all()
        return [entry.date for entry in entries]


@app.get("/api/entries/{entry_date}", response_model=JournalEntry)
def get_entry(entry_date: str):
    with Session(engine) as session:
        entry = session.exec(
            select(JournalEntry).where(JournalEntry.date == entry_date)
        ).first()
        if not entry:
            raise HTTPException(
                status_code=404, detail=f"Entry not found for date {entry_date}"
            )
        return entry


@app.post("/api/entries/", response_model=JournalEntry)
def save_entry(entry: JournalEntry):
    with Session(engine) as session:
        # Add or update entry.
        db_entry = session.exec(
            select(JournalEntry).where(JournalEntry.date == entry.date)
        ).first()
        if db_entry:
            db_entry.text = entry.text
            session.add(db_entry)
        else:
            session.add(entry)
        session.commit()

        output_text = base_chain.run(
            entry=entry.text,
            stop=[],
        )

        entry.analysis_text = output_text

        return entry


def diary_to_text(diary_entries: list[str]) -> str:
    entry_string = ""
    for _, entry in enumerate(diary_entries):
        entry_string = entry_string + f"""\n<entry>{entry}</entry>"""
    return entry_string


def put_in_perspective(input_list):
    context_prompt_combo = PromptTemplate(
        input_variables=["entry", "diary"], template=context_prompt_text_combo
    )
    chain = LLMChain(
        llm=anthropic_chat_llm,
        prompt=context_prompt_combo,
        llm_kwargs={"max_tokens_to_sample": 700},
    )
    output_text = chain.run(
        diary=diary_to_text(input_list[:-1]),  # TO BE REPLACED with actual input
        entry=input_list[-1],  # TO BE REPLACED with actual input
        stop=[],
    )

    logger.debug(f"Raw output: {output_text}")

    lookback_text = re.compile(r"<synthesis>(.*?)</synthesis>", re.DOTALL).findall(
        output_text
    )[0]
    day_in_context_text = re.compile(r"<response>(.*?)</response>", re.DOTALL).findall(
        output_text
    )[0]

    logger.debug(f"Lookback: {lookback_text}")

    logger.debug(f"Day in context: {day_in_context_text}")

    final_string = f"""# A lookback
{lookback_text}

# Your day in context
{day_in_context_text}
"""

    return final_string


@app.get("/api/today-and-last-x-days/", response_model=str)
def compare_today_with_last_x_days(n_days: int = 7):
    today = datetime.datetime.now()
    dates = sorted([today - datetime.timedelta(days=x) for x in range(n_days)])
    formatted_dates = [x.strftime("%Y-%m-%d") for x in dates]
    text_entries = []
    for x in formatted_dates:
        try:
            text_entries.append(get_entry(x))
        except HTTPException:
            if x != formatted_dates[-1]:
                continue

    return put_in_perspective(text_entries)
