from playwright.sync_api import sync_playwright
import json

def get_token_automatically():
    print("ok")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        # YouTube stores the PoToken in a JS object called 'ytcfg'
        token = page.evaluate("ytcfg.get('INNERTUBE_CONTEXT').serviceIntegrityDimensions.poToken")
        visitor_data = page.evaluate("ytcfg.get('INNERTUBE_CONTEXT').client.visitorData")
        
        browser.close()
        return {"po_token": token, "visitor_data": visitor_data}
print(get_token_automatically())