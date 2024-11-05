import sqlite3  
import json  
from openai import OpenAI  
import streamlit as st  
 
# Constants  
GPT_MODEL = "gpt-4o"  
client = OpenAI(api_key=st.secrets["OpenAI_key"])  
 
# Database connection  
conn = sqlite3.connect("dane_testowe.db")  
print("Opened database successfully")  
 
# Database utility functions  
def get_table_names(conn):  
    """Return a list of table names."""  
    table_names = []  
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")  
    for table in tables.fetchall():  
        table_names.append(table[0])  
    return table_names  
 
def get_column_names(conn, table_name):  
    """Return a list of column names."""  
    column_names = []  
    columns = conn.execute(f"PRAGMA table_info('{table_name}');").fetchall()  
    for col in columns:  
        column_names.append(col[1])  
    return column_names  
 
def get_database_info(conn):  
    """Return a list of dicts containing the table name and columns for each table in the database."""  
    table_dicts = []  
    for table_name in get_table_names(conn):  
        columns_names = get_column_names(conn, table_name)  
        table_dicts.append({"table_name": table_name, "column_names": columns_names})  
    return table_dicts  
 
# Get database schema information  
database_schema_dict = get_database_info(conn)  
example_data = {  
    "Miesiac": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],  
    "Centrum kosztów": ["Dział Finansów", "Dział HR", "Dział Marketingu", "Dział Sprzedaży"],  
    "Konto": ["411-01", "411-05", "411-07"],  
    "Nazwa konta": [  
        "Koszty materiałów biurowych",  
        "Koszty prezentów okolicznościowych",  
        "Koszty szkoleń i operacyjne",  
    ],  
    "Opis": ["Zakup materiałów biurowych", "Prezent dla klienta", "Szkolenie pracowników"],  
    "Kwota": ["100.00", "200.00", "300.00"]  
}  
 
database_schema_string = "\n".join(  
    [  
        f"Nazwa tabeli: {table['table_name']}\nKolumny: {', '.join(table['column_names'])}\nPrzykładowe dane: {', '.join(f'{col}: {example_data[col][0]}' for col in table['column_names'] if col in example_data)}. Dane są jedynie dla roku 2024"  
        for table in database_schema_dict  
    ]  
)  
 
# Define function to query the database  
def ask_database(conn, query):  
    """Function to query SQLite database with a provided SQL query."""  
    try:  
        results = str(conn.execute(query).fetchall())  
    except Exception as e:  
        results = f"query failed with error: {e}"  
    return results  
 
# Initialize Streamlit app  
st.title("Q&A")  
 
if "messages" not in st.session_state:  
    st.session_state.messages = []  
 
for message in st.session_state.messages:  
    with st.chat_message(message["role"]):  
        st.markdown(message["content"])  
 
# Handle user input  
if prompt := st.chat_input("What is up?"):  
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):  
        st.markdown(prompt)  
 
    # Prepare tools for OpenAI  
    tools = [  
        {  
            "type": "function",  
            "function": {  
                "name": "ask_database",  
                "description": "Use this function to answer user questions. Input should be a fully formed SQL query.",  
                "parameters": {  
                    "type": "object",  
                    "properties": {  
                        "query": {  
                            "type": "string",  
                            "description": f"""  
                                    SQL query extracting info to answer the user's question.  
                                    SQL should be written using this database schema:  
                                    {database_schema_string}  
                                    The query should be returned in plain text, not in JSON.  
                                    """,  
                        }  
                    },  
                    "required": ["query"],  
                },  
            }  
        }  
    ]  
 
    # Create initial message list  
    messages = [{"role": "user", "content": prompt}]  
 
    # Get response from OpenAI  
    response = client.chat.completions.create(  
        model=GPT_MODEL,  
        messages=messages,  
        tools=tools,  
        tool_choice="auto"  
    )  
 
    # Append the response to messages  
    response_message = response.choices[0].message  
    messages.append(response_message)  
 
    tool_calls = response_message.tool_calls  
    if tool_calls:  
        # If true the model will return the name of the tool / function to call and the argument(s)  
        tool_call_id = tool_calls[0].id  
        tool_function_name = tool_calls[0].function.name  
        tool_query_string = json.loads(tool_calls[0].function.arguments)['query']  

        st.text(tool_query_string)
 
        # Call the function and retrieve results  
        if tool_function_name == 'ask_database':  
            results = ask_database(conn, tool_query_string)  
 
            messages.append({  
                "role": "tool",  
                "tool_call_id": tool_call_id,  
                "name": tool_function_name,  
                "content": results + "\nWszystkie koszty są w PLN."  
            })  
 
            # Invoke the chat completions API with the function response appended to the messages list  
            model_response_with_function_call = client.chat.completions.create(  
                model=GPT_MODEL,  
                messages=messages,  
            )  
            response_content = model_response_with_function_call.choices[0].message.content  
            st.session_state.messages.append({"role": "assistant", "content": response_content})  
            with st.chat_message("assistant"):  
                st.markdown(response_content)  
        else:  
            st.error(f"Error: function {tool_function_name} does not exist")  
    else:  
        # Model did not identify a function to call, result can be returned to the user  
        st.session_state.messages.append({"role": "assistant", "content": response_message.content})  
        with st.chat_message("assistant"):  
            st.markdown(response_message.content)  