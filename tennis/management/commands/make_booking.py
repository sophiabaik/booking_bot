from django.core.management.base import BaseCommand

from django.contrib.auth.models import User
from tennis.models import UserProfile
from tennis.models import CourtLocation
from tennis.models import BookingParameter
from tennis.models import Booking

import time
import datetime

# import pytest
import time

import json

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as ec


from .spotery_constants import *

CHROMEDRIVER_PATH = 'WebDriver/bin/chromedriver'



booking_datetime = LOCAL_TIME_ZONE.localize(datetime.datetime(2020, 1, 12, 7, 30), is_dst=True)

court_location = 'Alice Marble'



def check_desired_date(booking_datetime):
    now = LOCAL_TIME_ZONE.localize(datetime.datetime.now(), is_dst=True)
    max_booking_date = now + datetime.timedelta(days=MAX_LOOKAHEAD_DAYS, hours=-CALENDAR_ADVANCE_TIME)

    if booking_datetime.date() > max_booking_date.date():
        raise ValueError('Desired booking date {} is more than {} days ahead of current datetime, {}'.format(
            booking_datetime.strftime("%a, %b %d, %Y at %I:%M %p %Z"),
            MAX_LOOKAHEAD_DAYS,
            now.strftime("%a, %b %d, %Y at %I:%M %p %Z")
        ))


def authenticate(root_url, login_email, login_password):
    
    driver = webdriver.Chrome(CHROMEDRIVER_PATH)

    driver.get(ROOT_URL)   
    driver.find_element(By.LINK_TEXT, "login / sign up").click()

    # Since we're loading a new page with unknown auth format, 
    # We need a try/except block next, so we sleep, rather than using WebDriverWait.until()
    time.sleep(LONG_POLE_WAIT)

    try:
        driver.find_element(By.LINK_TEXT, "Not your account?").click()
    except:
        pass

    driver.find_element(By.ID, "1-email").send_keys(LOGIN_EMAIL)
    driver.find_element(By.NAME, "password").click()
    driver.find_element(By.NAME, "password").send_keys(LOGIN_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, ".auth0-label-submit").click()
    return driver


def search_for_date(driver, booking_datetime):
    # Set month in calendar search widget
    dropdown = WebDriverWait(driver, DRIVER_WAIT).until(
            ec.presence_of_element_located((By.XPATH, "//select[@class='xos']")))
    
    dropdown.find_element(By.XPATH, "//option[. = '{}']".format(booking_datetime.strftime("%B"))).click()

    # Set year in calendar search widget
    year_select = driver.find_element(By.XPATH, "//input[@class='xjq']")
    year_select.clear()
    year_select.send_keys(booking_datetime.year)

    # The dates only update after click outside of the year input box
    # If we click "enter", it activates search (prematurely), so we click on a random div
    driver.find_element(By.XPATH, "//span[text()='San Francisco Recreation & Parks']").click()

    # Set day in calendar search widget
    # class xod is for days in the next month, xof is the previous month, xoe is current month
    driver.find_element(By.XPATH, "//td[@class='xoe' and text()='{}']".format(booking_datetime.day)).click()

    # Advance to search page
    driver.find_element(By.LINK_TEXT, "search").click()


def identify_relevant_courts(driver, court_location):
    # Wait for the divs with the courts to load, class xt7
    WebDriverWait(driver, DRIVER_WAIT).until(
            ec.presence_of_element_located((By.CSS_SELECTOR, ".xt7")))

    return driver.find_elements(By.XPATH, "//span[contains(text(),'{}')]".format(court_location))


def find_booking_link(driver, court_link, court_location):
    court_name = court_link.text
    
    court_div = court_link.find_element_by_xpath('..'
        ).find_element_by_xpath('..'
        ).find_element_by_xpath('..'
        ).find_element_by_xpath('..'
        ).find_element_by_xpath('..')
    
    booking_links = court_div.find_elements_by_link_text('{}'.format(booking_datetime.strftime("%I:%M %p")))
    
    if len(booking_links) == 0:
        raise ValueError('{} is not a valid booking time for {}'.format(
            booking_datetime.strftime("%I:%M %p"), court_location))
    else:
        return booking_links[0], court_name
        

def check_booking_availability(driver, booking_link):
    return len(
        booking_link.find_element_by_xpath('..'
        ).find_element_by_xpath('..'
        ).find_element_by_xpath('..'
        ).find_elements_by_xpath(".//span[text()='Booked']")
    ) == 0


def check_reached_use_booking_limit(driver, booking_datetime):
    time.sleep(LONG_POLE_WAIT)
    user_reached_limits_modal = driver.find_elements(By.XPATH, 
    	"//div[text()='You have reached the limit of bookings allowed on this Spot']")
    if len(user_reached_limits_modal) == 1:
        raise ValueError('User already has a booking on {}'.format(booking_datetime.strftime("%a, %b %d, %Y")))
    return 
    

def make_booking(driver, booking_link):
    booking_link.click()
    
    check_reached_use_booking_limit(driver, booking_datetime)
        
    # Some of the "Book Now" buttons are blocked by the "Support button"
    # So we remove this overlaid element with some embedded JavaScript
    # The overlay is present from the original page load, so we don't have to wait for it
    overlay = WebDriverWait(driver, DRIVER_WAIT).until(
        ec.presence_of_element_located((By.XPATH, "//iframe[@title='Opens a widget where you can find more information']")))
    driver.execute_script("""
        var element = arguments[0];
        element.parentNode.removeChild(element);
    """, overlay)

    WebDriverWait(driver, DRIVER_WAIT).until(
        ec.presence_of_element_located((By.LINK_TEXT, 'Book Now'))).click()

    # Confirmation page loads
    confirmation_span = WebDriverWait(driver, DRIVER_WAIT).until(
        ec.presence_of_element_located((By.XPATH, "//span[contains(text(),'Reservation # ')]")))
    
    # Note: we refer to this as the booking number, to be consistent with the general
    # use of "booking" in this codebase, but Spotery calls this a reservation number
    booking_number = confirmation_span.text.split('#')[1].strip(' ')
    return booking_number
    

def confirm_successful_booking(booking_datetime, court_name, booking_number):
    print('You are confirmed for {} on {} from {}-{}, booking number {}'.format(
        court_name, 
        booking_datetime.strftime("%a, %b %d, %Y"),
        booking_datetime.strftime("%I:%M %p"),
        (booking_datetime + datetime.timedelta(minutes=BOOKING_LENGTH_MINUTES)).strftime("%I:%M %p"),
        booking_number
    ))


def confirm_unsuccessful_booking(booking_datetime, court_location):
    print('No available courts at {} on {}'.format(
        court_location, 
        booking_datetime.strftime("%a, %b %d, %Y at %I:%M %p")))


def book_court(root_url, login_email, login_password, booking_datetime, court_location):
    check_desired_date(booking_datetime)
    driver = authenticate(root_url, login_email, login_password)
    search_for_date(driver, booking_datetime)
    court_links = identify_relevant_courts(driver, court_location)
    
    booking_successful = False

    for court_link in court_links:
        booking_link, court_name = find_booking_link(driver, court_link, court_location)
        
        if booking_link is None:
            continue
        
        booking_available_indicator = check_booking_availability(driver, booking_link)
        
        if booking_available_indicator:
            booking_number = make_booking(driver, booking_link)
            return True, booking_number, court_name, None
            # booking_successful = True
            # confirm_successful_booking(booking_datetime, court_name, booking_number)
            break
    
    if not booking_successful:
        return False, None, None, confirm_unsuccessful_booking(booking_datetime, court_location)
        
   


class Command(BaseCommand):
	help = """python manage.py make booking
		Attempts to make a tennis court booking using Spotery SF.
		"""

	def handle(self, *args, **options):
		pending_bookings = Booking.objects.filter(status='Pending')
		pending_booking_count = len(pending_bookings) 
		
		for i, booking in enumerate(pending_bookings):
			print('Working on booking {} of {} for {}'.format(
					i + 1, pending_booking_count, booking.user
				))

			booking_successful, booking_number, court_name, failure_reason = book_court(
				ROOT_URL, 
				booking.user.user_profile.spotery_login,
				booking.user.user_profile.spotery_password,
				booking.datetime,
				booking.court_location
			)

			if booking_successful:
				booking.status = 'Succeeded'
				booking.booking_number = booking_number
				# TODO: align naming court_number = court_name
				booking.court_number = court_name
			else:
				booking.status = 'Failed'
				booking.failure_reason = failure_reason

			booking.save()





