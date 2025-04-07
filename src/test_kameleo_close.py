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
client = KameleoLocalApiClient(
  endpoint=f'http://localhost:{kameleo_port}',
  retry_total=0
)


def get_profiles_ids():
    kameleo_port = 5050
    profiles_url = f"http://localhost:{kameleo_port}/profiles"
    response = requests.get(profiles_url)

    ids = [profile['id'] for profile in response.json()]
    names = [profile['name'] for profile in response.json()]
    
    return dict(zip(names, ids))

profile_ids = get_profiles_ids()

pprint(profile_ids)

first_profile_id = list(profile_ids.values())[0]

browser_ws_endpoint = f'ws://localhost:{kameleo_port}/playwright/{first_profile_id}'

with sync_playwright() as playwright:
    browser = playwright.chromium.connect_over_cdp(endpoint_url=browser_ws_endpoint)

    page = browser.new_page()
    page.goto('https://www.google.com')
    page.wait_for_timeout(10000)

    client.stop_profile(first_profile_id)
    browser.close()



