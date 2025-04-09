import asyncio
import requests
import json
from playwright.async_api import async_playwright
import time
from kameleo.local_api_client import KameleoLocalApiClient
from pprint import pprint
from playwright.sync_api import sync_playwright
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.builder_for_create_profile import BuilderForCreateProfile
from kameleo.local_api_client.models import WebglMetaSpoofingOptions
from asyncio import run


kameleo_port = 5050
client = KameleoLocalApiClient()

base_profiles = client.search_base_profiles(
    device_type='desktop',
    browser_product='chrome'
)

pprint(base_profiles)

def get_profiles_ids():
    kameleo_port = 5050
    profiles_url = f"http://localhost:{kameleo_port}/profiles"
    response = requests.get(profiles_url)

    ids = [profile['id'] for profile in response.json()]
    names = [profile['name'] for profile in response.json()]
    
    return dict(zip(names, ids))



profile_ids = get_profiles_ids()
profile_ids = list(profile_ids.values())

first_id = profile_ids[0]

browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{first_id}'

try:
    client.start_profile(first_id)
except Exception as e:
    if "already running" in str(e):
        print("Browser already running")
    else:
        raise e

with async_playwright() as playwright:
  browser = playwright.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)
  context = browser.contexts[0]
  page = context.pages[0]

  page.goto('https://www.google.com')
  page.wait_for_timeout(10000)

  try:
    page.close()
    #client.stop_profile(first_id)
    print("Browser closed")
  except Exception as e:
    if "not running" in str(e):
      print("Browser not running")
    else:
      raise e
