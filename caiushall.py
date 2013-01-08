#!/usr/bin/python

import requests, bs4, datetime, io
import simplejson as json

# TODO: split into multiple classes for net and local methods
class CaiusHall():
    """
    Main class for the Caius Hall desktop application.

    Attributes:
        HALL_URL: the string url for the hall booking system
        RAVEN_AUTH_PAGE: the string url for the page required to authenticate into Raven
        RAVEN_STATUS_PAGE: the string url for the Raven status page
        CERTS: the string for the local path to a file containing the necessary SSL certs
        cookies: the list of cookies used when authenticating with Raven
        current_user: the string crsid of the last user to authenticate
        DATA_PATH: the path to save data to disk
        session: the current requests.Session object to make requests with
        hall_bookings: dict containing the current bookings made by the current_user
    """

    def __init__(self):
        # TODO: extract constants to separate file
        self.HALL_URL = 'https://www.cai.cam.ac.uk/mealbookings/index.php'
        self.RAVEN_AUTH_PAGE = 'https://raven.cam.ac.uk/auth/authenticate2.html'
        self.RAVEN_STATUS_PAGE = 'https://raven.cam.ac.uk/auth/status.html'
        self.CERTS = 'certs.pem'
        self.cookies = None
        self.current_user = None

        # save to local directory
        self.DATA_PATH = ''

        # Construct the requests session object
        self.session = requests.Session()
        self.session.verify = self.CERTS

        self.hall_bookings = {}

    def auth(self, crsid, password):
        """
        Authenticates a user with the Caius Hall Booking system.

        Args:
            crsid: The user's crsid (Raven username)
            password: The user's password

        Returns:
            A boolean value corresponding to the success or failure of the authentication attempt.
            Note: If the user is already logged in, True is returned.

        """

        if (crsid == self.current_user):
            # our current_user wants to re-login
            if (self.is_authed()):
                # user is already logged in, no action needed
                print('User ' + crsid + ' is already logged in.')
                return True
                # no cookies set, need to log in with Raven

        # Begin login procedure here, both for different users and expired sessions

        data = {'userid': crsid, 'pwd': password}
        r = self.session.post(self.RAVEN_AUTH_PAGE, data=data, allow_redirects=False)

        if(r.status_code == 302):
            # server sent us a 302 redirect, check that the redirect is taking us to
            # the status page
            if (r.headers['location'] == self.RAVEN_STATUS_PAGE):
                # if all goes well, we should end up here
                # set the cookies for future auths and the current user's crsid
                self.cookies = r.cookies
                self.current_user = crsid
                print("Successfully logged in user " + crsid + '.')
                self.load_local_bookings()
                return True
            else:
                # find the error using html parsing (only parse span.error)
                # TODO: any way to streamline this code?
                error_span_tags = bs4.SoupStrainer('span', class_='error')
                soup = bs4.BeautifulSoup(r.text, parse_only=error_span_tags)
                errors = soup.find_all('span', class_='error')
                if (len(errors) > 0):
                    print ('Error: Server responded - ' + errors[0].text)
                else:
                    print('Error: Received a good response from server, but the page returned was unexpected.')
                return False
        else:
            print('Error: Authentication failed - server responded with error code ' + str(r.status_code))
            return False

    def is_authed(self):
        """
        Checks if there is a user currently authenticated with the server.

        Cookies are checked, and if they exist, we make a GET request to the hall
        server and determine whether we are logged in from the response URL.

        Returns:
            A boolean value. True if there is a user currently authenticated, and false otherwise.
        """

        if (not self.cookies):
            # no cookies, not logged in
            return False
        else:
            # make a request to the hall server and check its url
            r = self.session.get(self.HALL_URL, cookies=self.cookies)
            if (self.HALL_URL == r.url):
                return True
            else:
                self.cookies = None
                self.current_user = None
                return False


    def logout(self):
        """
        Logs the current user out of the server.

        We create a new session object and remove the previous cookies. The value of current_user
        is also reset.
        """

        self.hall_bookings = {}

        # Create a new session object
        self.session = requests.Session()
        self.session.verify = self.CERTS

        self.current_user = None
        self.cookies = None
        print('Logged out of Raven.')

    def load_local_bookings(self):
        """
        Loads the user's bookings from disk into self.hall_bookings.

        A current_user must be specified in order to load bookings. The data is currently
        stored in json format in the DATA_PATH directory, under the name <current_user>_data.json.
        """
        if (self.current_user):
            try:
                with io.open(self.DATA_PATH + self.current_user + '_data.json', 'rb') as infile:
                    self.hall_bookings = json.load(infile)
            except IOError as e:
                print ('No data file found for user ' + self.current_user + '.')
                pass
        else:
            print('Error: no current user specified - cannot load local bookings.')

    def save_local_bookings(self):
        """
        Saves the user's bookings to disk, from self.hall_bookings.

        A current_user must be specified. The data is currently stored in json format
        in the DATA_PATH directory, under the name <current_user>_data.json.
        """
        if (self.current_user):
            with io.open(self.DATA_PATH + self.current_user + '_data.json', 'wb') as outfile:
                json.dump(self.hall_bookings, outfile)
        else:
            print('Error: no current user specified - cannot save local bookings.')

    def local_book_hall(self, utc_date, type, special_info = '', vegetarian = False, requirements = ''):
        """
        Books hall locally, and saves the data to disk.

        An entry is added to the local hall_bookings dictionary, and then saved with
        save_local_bookings(). This has no effect on the server's bookings.

        Args:
            utc_date: the datetime.datetime object representing the utc time for the booking
            type: a string of either 'first' or 'formal'
            special_info: optional string - if the booking has additional information such
                as 'celebrating the queen's jubilee' or 'early hall due to matriculation dinner'
            vegetarian: optional boolean - defaults to false
            requirements: optional string - any additional requirements such as 'Vegan please'
                or 'I am allergic to <x>!' - to be used in the requirements box that the
                kitchen sees
        """
        utc_date_string = utc_date.strftime('%Y-%m-%d %H:%M')

        day = utc_date.strftime('%A')
        time = utc_date.strftime('%H:%M')

        # The booking is considered special if the time and day aren't the expected
        special = not ((time == '18:15' and type == 'first')
                    or (time == '19:20' and type == 'formal' and day != 'Sunday')
                    or (time == '19:30' and type == 'formal' and day == 'Sunday'))

        data = {
            'utc_date': utc_date_string,
            'type': type,
            'special': special,
            'special_info': special_info,
            'vegetarian': vegetarian,
            'requirements': requirements
        }

        self.hall_bookings[utc_date_string] = data
        self.save_local_bookings()

    def local_cancel_hall(self, utc_date):
        """
        Cancels (deletes) a local hall booking and saves the data to disk.

        This has no effect on the server's bookings.

        Args:
            utc_date: the datetime.datetime object representing the utc time for the booking
                that is to be cancelled

        Returns:
            A boolean value. True if an entry was found and deleted for the specified date,
            false otherwise.
        """
        utc_date_string = utc_date.strftime('%Y-%m-%d %H:%M')
        if (utc_date_string in self.hall_bookings):
            del self.hall_bookings[utc_date_string]
            self.save_local_bookings()
            return True
        else:
            print 'Error: no booking found for the date chosen'
            return False

# TODO: unit tests
