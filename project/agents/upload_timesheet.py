# import config as CONFIG
# from langchain_openai import ChatOpenAI
# from browser_use import Agent
# import asyncio
# from typing import Optional

    
# # Initialize LLM if not provided
# llm = ChatOpenAI(model=CONFIG.model, temperature = 0.3)

# async def zoho_login_and_navigate(
#     email: str,
#     password: str,
#     zoho_url: str,
#     timesheet_wait: int = 3  # seconds to wait for page loads
# ) -> None:
#     """
#     Automates the Zoho People login process and navigates to the Timesheet section.
    
#     Args:
#         email (str): Your Zoho account email
#         password (str): Your Zoho account password
#         llm (ChatOpenAI, optional): Language model instance. If None, will use default settings
#         zoho_url (str, optional): Base URL for Zoho People. Default is standard URL
#         timesheet_wait (int, optional): Wait time in seconds for page loads
#     """


#     # Create steps for login process
#     # login_steps = [
#     #     # Step 1: Open browser and navigate to Zoho
#     #     f"Open a new browser window and navigate to {zoho_url}",
        
#     #     # Step 2: Enter email
#     #     f"Locate the email input field and enter: {email}",
#     #     "Press Enter after entering the email",
        
#     #     # Step 3: Enter password
#     #     f"Wait for the password field to appear, then enter: {password}",
#     #     "Press Enter after entering the password",
        
#     #     # Step 4: Navigate to Time Sheet
#     #     f"Wait {timesheet_wait} seconds for the page to load completely",
#     #     # f"Wait an additional {timesheet_wait} seconds for dynamic content to load",
#     #     "Find the 'Organization', which is usually on the top navigation bar and click on that"

#     #     # Step 5: Navigate to Timesheets tab
#     #     f"Wait {timesheet_wait} seconds for the page to load completely",
#     #     "In the organization page, find for the 'page-id='services'', in this <div> there is <ul>, so find the <ul> element",
#     #     "Within the <ul>, find the <li> element that contains the text 'Time Sheet'",
#     #     "Click on this list item element or any clickable element within it that contains 'Time Sheet'",
        
#     #     # "Find a list item containing 'Time Sheets' in the sidebar navigation menu (typically within a ul element) and click it. The element might be within a collapsed menu that needs to be expanded first",
#     #     # f"Find the 'Time Sheets' and click on that"

#     #     # Step 6: Navigate to Timesheets tab
#     #     f"Wait {timesheet_wait} seconds for the page to load",
#     #     "Click on the 'Timesheets' tab"
#     # ]
    
#     # # Join steps into a single task description
#     # task_description = " Then ".join(login_steps)
    
#     # # Create and run the agent
#     # agent = Agent(
#     #     task=task_description,
#     #     llm=llm
#     # )


#     login_task = f"""
#     1. Open a new browser window
#     2. Navigate to {zoho_url}
#     3. Wait for the email input field to be visible
#     4. Click on the email input field
#     5. Type: {email}
#     6. Press the Enter key
#     7. Wait for the password input field to become visible
#     8. Click on the password input field
#     9. Type: {password}
#     10. Press the Enter key
#     11. Wait {timesheet_wait} seconds for the page to load completely

#     1. look for 'Time Sheets' in the sidebar <ul> > <li> and mouse click on that,      

#     2. Wait {timesheet_wait} seconds for the page to update
#     3. click on more icon on page, and click on import 
    
#     4. Wait {timesheet_wait} seconds for the page to update
#     5. click 'Import File' button on page

#     """

#     # 6. Move the mouse to that text location
#     # 7. Click on the element or its nearest clickable parent
#     # 5. Look for any element containing the exact text "Timesheets"
#     # 1. Navigate to this given link 'https://people.zoho.com/indexnine/zp#timetracker/mydata/timelogs-mode:list'


#     try:
#         # Execute login
#         agent = Agent(
#             task=login_task,
#             llm=llm
#         )
#         abc = await agent.run()
#         await asyncio.sleep(timesheet_wait)

#         # # Execute navigation
#         # agent = Agent(
#         #     task=navigation_task,
#         #     llm=llm
#         # )
#         # await agent.run()

#     except Exception as e:
#         print(f"Automation error occurred: {str(e)}")
#         raise


# async def main():
#     await zoho_login_and_navigate(
#         email=CONFIG.email,
#         password=CONFIG.password,
#         zoho_url=CONFIG.zoho_url,
#         timesheet_wait=5  # Increase wait time if pages load slowly
#     )

# if __name__ == "__main__":
#     asyncio.run(main())

# ------------------------------------------------------

import config as CONFIG
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from browser_use import Agent
import asyncio
from typing import Optional
import os

# Initialize LLM if not provided
llm = ChatOpenAI(model=CONFIG.model, temperature=0.0)
# llm = ChatAnthropic(model=CONFIG.model, temperature=0.0)

async def zoho_login_and_navigate(
    email: str,
    password: str,
    zoho_url: str,
    timesheet_wait: int = 3
) -> None:
    """
    Automates the Zoho People login process, navigation, and file upload.
    
    Args:
        email (str): Your Zoho account email
        password (str): Your Zoho account password
        zoho_url (str): Base URL for Zoho People
        file_path (str): Path to the timesheet file for upload
        timesheet_wait (int): Wait time in seconds for page loads
    """
    
    # Verify file exists before starting automation
    # if not os.path.exists(file_path):
    #     raise FileNotFoundError(f"Timesheet file not found at: {file_path}")

    # Get absolute file path for upload
    # abs_file_path = os.path.abspath(file_path)

    login_task = f"""
    1. Open a new browser window
    2. Navigate to {zoho_url}
    3. Wait for the email input field to be visible
    4. Click on the email input field
    5. Type: {email}
    6. Press the Enter key
    7. Wait for the password input field to become visible
    8. Click on the password input field
    9. Type: {password}
    10. Press the Enter key
    11. Wait {timesheet_wait} seconds for the page to load completely

    12. Look for 'Time Sheets' in the sidebar <ul> > <li> and mouse click on that
    13. Wait {timesheet_wait} seconds for the page to update

    14. Now look for the 'Log Time' button and click on that

        16. For filling out the form, follow these steps precisely:
        a. Find and click the input field labeled 'Project Name'
        b. Wait for the dropdown to appear
        c. Look for and select exactly 'Snap.core - P0089' from the options
        d. Wait {timesheet_wait} seconds for selection to register

        e. Find and click the input field labeled 'Job Name', click on that field,
        f. There will be search box field (input field wihch has class attribute is 'zdropdownlist__searchfield') in that type 'Time' in that search box
        g. Look for and select exactly 'Time', click to select it
        h. Wait {timesheet_wait} seconds for selection to register

        i. Locate the input field labeled 'Work Item'
        j. Click the field and type exactly: 'I have done devvv'

        k. Find the 'Date' field
        l. Click to open the date picker
        m. Select date '07' of the current month
        n. Wait for date selection to register

        o. Find the input field labeled 'Description'
        p. Click the field and type exactly: 'I told you this is description'

        q. Locate the input field labeled 'Hours'
        r. Click the field and type exactly: '10:30'



    





    
    """

    # 17. After all fields are filled:
    # a. Look for a button labeled 'Save' or containing the text 'Save'
    # b. Click the Save button
    # c. Wait {timesheet_wait} seconds for the save operation to complete

    # 15. Now you have to fill the form according to below given information
    #     15.1. Click on the 'Project Name' input field, and click on 'TJ- NDC Airline Integration - P0083' from the given options dropdown.
    #     15.2. Then click on the 'Job Name' field and scroll slowly until you see the 'Dev - Development' and select 'Dev - Development' option
    #     15.3. Then in the 'Work Item' put this 'I have done devvv'
    #     15.4. Then in th 'Date' field, pick '06' date 
    #     15.5. Then in the 'Description' write this 'I told you this is description'
    #     15.6. Then  in the 'Hours' field fill this '10:30'
    # 16. Now after filling the for, look for the save button and click on that

    # 14. Click on more icon on page, and click on import
    
    # 16. Look for an input element of type 'file' on the page
    # 17. Once found, use the input element to select the file at: {abs_file_path}
    
    # 20. Wait {timesheet_wait * 2} seconds for the file to be processed
    # 21. Look for any confirmation buttons or 'Submit' buttons and click them

    try:
        agent = Agent(
            task=login_task,
            llm=llm
        )
        result = await agent.run()
        await asyncio.sleep(timesheet_wait)
        
    except Exception as e:
        print(f"Automation error occurred: {str(e)}")
        raise

async def main():
    await zoho_login_and_navigate(
        email=CONFIG.email,
        password=CONFIG.password,
        zoho_url=CONFIG.zoho_url,
        timesheet_wait=1
    )
    # file_path="C:\IDX\AI\Browser-use\Timesheet_test\.venv\project\TimeLogImport_Template_UPDATED_TEST.xlsx",  # Specify your file path here

if __name__ == "__main__":
    asyncio.run(main())