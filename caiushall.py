#!/usr/bin/python

import requests
import bs4

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
    """

    def __init__(self):
        # TODO: extract constants to separate file
        self.HALL_URL = 'https://www.cai.cam.ac.uk/mealbookings/index.php'
        self.RAVEN_AUTH_PAGE = 'https://raven.cam.ac.uk/auth/authenticate2.html'
        self.RAVEN_STATUS_PAGE = 'https://raven.cam.ac.uk/auth/status.html'
        self.CERTS = 'certs.pem'
        self.cookies = None
        self.current_user = None

    def auth(self, crsid, password, attempt=1):
        """
        Authenticates a user with the Caius Hall Booking system.

        Includes checks to ascertain whether the user is already logged in.

        Args:
            crsid: The user's crsid (Raven username)
            password: The user's password
            attempt: The current count of attempts in this loop (prevents perpetual looping)

        Returns:
            A boolean value corresponding to the success or failure of the authentication attempt.
            Note: If the user is already logged in, True is returned.

        """
        if (attempt > 2):
            print('Error: Something sent the authentication process into a loop!')
            return False
        elif (self.cookies):
            # we have cookies set for self.current_user
            if (crsid == self.current_user):
                # requested user already has cookies
                # let's check if our session is still alive
                # TODO: possible to check session without using a request?
                r = requests.get(self.HALL_URL, cookies=self.cookies, verify=self.CERTS)
                if(r.status_code == requests.codes.ok):
                    if (r.url != self.HALL_URL):
                        # our session has expired, try again
                        self.cookies = None
                        self.current_user = None
                        print('Session appears to have expired for current user, trying again...')
                        self.auth(crsid, password, attempt+1)
                    else:
                        print('User ' + crsid + ' is already logged in.')
                        return True
                else:
                    print('Error: Authentication failed - ' + r.headers.status)
                    return False
            else:
                # log in with different crsid, remove cookies
                self.cookies = None
                self.current_user = None
                print('Different user requested, logging into new account...')
                self.auth(crsid, password, attempt+1)

        else:
            # no cookies set, need to log in with Raven
            data = {'userid': crsid, 'pwd': password}
            r = requests.post(self.RAVEN_AUTH_PAGE, params=data, verify=self.CERTS)

            if(r.status_code == requests.codes.ok):
                # server sent us a 200 OK
                if (r.url == self.RAVEN_STATUS_PAGE):
                    # if all goes well, we should end up here
                    # set the cookies for future auths and the current user's crsid
                    self.cookies = r.cookies
                    self.current_user = crsid
                    print("Successfully logged in user " + crsid + '.')
                    return True
                else:
                    # find the error using html parsing (only parse span#error)
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
                print('Error: Authentication failed - ' + r.headers.status)
                return False