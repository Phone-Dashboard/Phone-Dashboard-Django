# Phone Dashboard Data Collection Server

This document describes how to install the Phone Dashboard data collection server. It assumes competency with the Linux operating system, the Postgres database, and the Django web application framework.

## Data Collection Server Design

The Phone Dashboard data collection server (DCS) is designed to receive de-identified data from Phone Dashboard mobile app to separate study data from personally-identifiable information in the interests of overall information security and preserving participant privacy.

When the extension transmits data to the DCS, only the participant identifier is sent to identify the source of the transmission - the app itself discards the personal information used for lookup as soon as it retrieves a participant identifier.

The DCS is built on [the Passive Data Kit Django platform](https://github.com/audacious-software/PassiveDataKit-Django/) (PDK) to use existing data collection and processing infrastructure that has powered observational and experimental studies for many years. Investigative teams seeking to deploy Phone Dashboard for their studies are **strongly** encouraged to review the PDK documentation and [the Django web application framework](https://www.djangoproject.com/start/) used by PDK. The Phone Dashboard DCS builds heavily on both platforms and uses conventions, techniques, and tools native to both.

## Prerequisites

A Unix-like OS with access to root/sudo: 
* CRON
* Python 3.6+
* Apache2 web server with [mod_wsgi](https://modwsgi.readthedocs.io/)
* A domain name with an SSL certificate that is pointed to a publicly-addressable IP address (or suitable web application firewall that forwards traffic to the DCS)
* Postgres database 9.5+ with PostGIS extensions

Typically, the bundled Apache server and mod_wsgi module that comes with your Unix distribution will support Django.

In addition to the standard background jobs provided by PDK ([more details here](https://github.com/audacious-software/PassiveDataKit-Django/#background-jobs-setup)), the DCS adds several additional jobs for tasks such as extracting Amazon ASIN identifiers from the data sent by browsers and generating nightly data export jobs that bundle the past day's data collection into a form suitable for study monitoring and analysis.

*Note that many of these tasks (such as compiling a large data report) will often run longer than the typical request timeout window web servers or clients will tolerate, so chaining these requests to HTTP endpoints that are triggered by an outside polling service **will not** be sufficient for these purposes as a CRON substitute.*

## Installation

1. Verify that your system meets the requirements above and install any needed components. *This example provides commands for a Debian-Ubuntu based OS*. Any Linux-based OS will be conceptually similar, but will require different syntax.
   * Make sure you have sudo access `sudo echo "Sudo access confirmed"`
   * Verify your public IP or Domain: `curl ifconfig.me`
   * Update your OS package manager, e.g. `sudo apt update`
   * Verify Cron access `sudo systemctl status cron`
   * Check your Python version `python3 --version`
   * The following are basic utilities you will need that may not be included in a fresh installation.
     ```
     sudo apt install python3-pip
     sudo apt-get install dialog
     sudo apt-get install apt-utils
     sudo apt install git
     sudo apt install python3-venv
     ```
   * Verify that you have Postgres 9.5+ and the PostGIS extension (this extension is needed to setup Phone Dashboard, whether or not you plan to collect geographic information).
     ```
     psql --version
     sudo -u postgres psql -c "SELECT PostGIS_Version();" # change postgres to your database user if different
     ```
   * Verify that you have Apache2 with [mod_wsgi](https://modwsgi.readthedocs.io/)
     ```
     apache2 -v
     sudo apachectl -M | grep wsgi
     ```

1. **(Strongly Recommended)** Before installing the DCS, [create a Python virtual environment](https://docs.python.org/3/library/venv.html) that will contain the local Python environment and all of the relevant dependencies separate from your host platform's own Python installation. *Do not put this virtual environment in your home directory, which is not accessible to Apache*, a suggestion is to create a directory such as `/var/www/venvs/dcs` to put it in. then create it once you are in the appropriate directory `python3 -m venv myvenv`  Don't forget to activate your virtual environment before continuing (and every time you make changes)! e.g. `source /var/www/venvs/dcs/myvenv/bin/activate`

2. Clone this repository to a suitable location on your server:

    ```
    $ git clone [https://github.com/Phone-Dashboard/Phone-Dashboard-Django.git](https://github.com/Phone-Dashboard/Phone-Dashboard-Django.git) /var/www/phone_dashboard
    $ cd /var/www/phone_dashboard
    ```

    Initialize the Git submodules:

    ```
    git submodule init
    git submodule update
    ```

3. Create a suitable Postgres database as the local `postgres` (or equivalent) user:

    ```
    $ sudo su - postgres
    $ psql
    postgres=# CREATE USER phone_dashboard WITH PASSWORD 'XXX' LOGIN;
    postgres=# CREATE DATABASE phone_dashboard_data WITH OWNER phone_dashboard;
    postgres=# exit
    ```

    (Replace `XXX` with a strong password.)

    After the database has been created, enable the PostGIS extension:

    ```
    $ psql phone_dashboard_data
    postgres=# CREATE EXTENSION postgis;
    postgres=# exit
    ```

    After the PostGIS extension has been enabled, you may log out as the local `postgres` user.

4. Back in the DCS directory, install the Python dependencies:

    ```
    $ pip install wheel
    $ pip install -r requirements.txt
    ```

    Installing the `wheel` package before the rest of the Python dependencies allow the system to use pre-compiled packages, which may save signicant time spent building Python modules and tracking down all of the system-level dependencies and development libraries needed.

5. Install and configure the `local_settings.py` file:

    ```
    $ cp phone_dashboard/local_settings.py-template phone_dashboard/local_settings.py
    ```

    Open the new `local_settings.py` file and [follow the configuration instructions within the file](/phone_dashboard/local_settings.py-template) to configure the server.
    
6. Once the server has been configured, initialize the database:

    ```$ ./manage.py migrate```

    Copy the static resource files to the appropriate location:

    ```$ ./manage.py collectstatic```

    Create a new superuser account to login to the server:

    ```$ ./manage.py createsuperuser```

7. If  you are not familiar with setting up an Apache2 website, see [this basic tutorial](https://ubuntu.com/tutorials/install-and-configure-apache#1-overview), if you are not using Ubuntu, there are similar tutorials for different Linux distributions. Make sure Apache is running properly by using `systemctl status apache2`.
 
8. Next, [configure your local Apache HTTP server](https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/modwsgi/) to connect to Django.

    Your must configure Django to be served over HTTPS ([obtain a Let's Encrypt certificate if needed](https://letsencrypt.org/)) and to forward any unencrypted HTTP requests to the HTTPS port using a `VirtualHost` definition like:

    ````
    <VirtualHost *:80>
        ServerName myserver.example.com

        RewriteEngine on
        RewriteRule    ^(.*)$    https://myserver.example.com$1    [R=301,L]
    </VirtualHost>
    ````

9. Change the postgres configuration to allow for password-based access by Django:
```
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Change the line from something like this:
```
# TYPE DATABASE USER ADDRESS METHOD 
local all all peer
```
to:
```
# TYPE DATABASE USER ADDRESS METHOD 
local all all md5
```
Then restart postgres
```
sudo systemctl restart postgresql
```

10. Once Apache is configured and running, login to the Django administrative backend using the user credentials created above: 

    `https://myserver.example.com/admin/` (Replace `myserver.example.com` with your own host's name.) 
    
Congratulations, you have installed the Phone Dashboard data collection server.

## Background Jobs Setup

Before your site is ready for use by clients, we have one more **very** important step to complete: setting up the background CRON jobs. Follow [the instructions for Passive Data Kit](https://github.com/audacious-software/PassiveDataKit-Django/#background-jobs-setup).

***

*This is an early initial version of this documentation, so if you have any questions or a topic was left unaddressed, please direct those inquiries to [chris@audacious-software.com](mailto:chris@audacious-software.com).*
