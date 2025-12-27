from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import numpy as np
import undetected_chromedriver as uc
driver = uc.Chrome()
driver.get("https://fanteziigreieriprostii.ro/")
# save html page of this url
with open("fanteziigreieriprostii.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
