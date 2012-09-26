'''
Created on Oct 25, 2010

@author: jeffrey lensen

'''

import os
import sys
import socket
from time import strftime
import simplejson
import urllib
import logging

import icinga

log = logging.getLogger(__name__)
current_time = strftime("%Y-%m-%d %H:%M:%S")

__config = icinga.parse_configfile(["icinga"])
api_app_id = __config["icinga"]["api_app_id"]
api_base_url = __config["icinga"]["api_base_url"]
proxies = simplejson.loads(__config["icinga"]["proxies"])

def icinga_search(searchtype, search_filter, search_columns, search_orderfield, search_orderdirection="ASC"):
    if api_app_id == "" or api_base_url == "":
        return None

    socket.setdefaulttimeout(10)

    if searchtype == "service":
        search_filter.append("SERVICE_IS_ACTIVE|=|1")
        search_filter.append("HOST_IS_ACTIVE|=|1")
    elif searchtype == "host":
        search_filter.append("HOST_IS_ACTIVE|=|1")

    filter='/filter[AND(%s)]' % ";".join(search_filter)
    columns='/columns[' + "|".join(search_columns) + ']'
    order='/order[' + search_orderfield + ';' + search_orderdirection + ']'
    authkey='/authkey=' + api_app_id
    output='/json'
    args = searchtype + filter + columns + order + authkey + output
    url = api_base_url + urllib.quote(args)
    log.debug("Search URL: %s%s" % (api_base_url, args))
    try:
        result = simplejson.load(urllib.urlopen(url, proxies=proxies))
        log.debug("Search result: %s" % result)
    except ValueError:
        log.debug("Could not run jsonload on result")
        return None
    except IOError, msg:
        log.warning("Failed to execute icinga search: %s" % (msg))
        return None
    try:
        return result['result']
    except:
        return None

def send_to_icinga(cmd,target):
    if api_app_id == "" or api_base_url == "":
        return None
    params = {}
    targetstr = "%s" % target

    socket.setdefaulttimeout(10)
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    params["cmd"] = cmd
    params["target"] = targetstr.replace(' \'', '\'')
    params["data"] = {}
    params["authkey"] = api_app_id
    args = "/cmd"
    for param in params:
        args = args + "/%s=%s" % (param, params[param])

    url = api_base_url + urllib.quote(args.replace('\'', '"'))
    log.debug("CMD URL: %s" % api_base_url + args.replace('\'', '"'))

    try:
        response = urllib.urlopen(url, proxies=proxies)
        log.debug(response.read())
        return response
    except:
        return None

def group(s, n): return [s[i:i+n] for i in xrange(0, len(s), n)]

def icinga_cmd(hostname=None, cmdlist=None, services=None, targetlist={}):
    targets = []
    if hostname is not None:
        log.debug("Searching for monitoring instance")
        instancehost = get_monitoring_host(hostname)
    if instancehost is None:
        log.warning("Skipping because no monitoring instance was found")
        return
    if cmdlist is None or services is None:
        log.critical("You need to specify a command and services")
        return

    targetlist["host"] = str(hostname)
    targetlist["instance"] = instancehost

    for cmd in cmdlist:
        for service in services:
            servicetargetlist = targetlist.copy()
            servicetargetlist["service"] = service
            targets.append(servicetargetlist)

        for targetgroup in group(targets, 35):
            send_to_icinga(cmd, targetgroup)
    return

def get_monitoring_host(hostname):
#    use this for >= 1.6
    icinga_result = icinga_search('instance', ['HOST_NAME|=|%s' % hostname], ['INSTANCE_NAME'], 'HOST_ID', 'DESC')
#    use this for < 1.6
#    icinga_result = icinga_search('host', ['HOST_NAME|=|%s' % hostname], ['INSTANCE_NAME'], 'HOST_ID', 'DESC')
    if icinga_result is not None and icinga_result != []:
        try :
            instancehost = icinga_result[0]['INSTANCE_NAME']
            log.debug("%s is monitored by %s" % (hostname, instancehost))
            return instancehost
        except:
            log.warning("Could not determine monitoring host for %s" % hostname)
            return None
    else:
        log.debug("API did not return a monitoring host (%s)" % icinga_result)
        return None

    log.warning("Could not determine monitoring host for %s" % hostname)
    return None

def get_services(hostname):
    log.debug("Searching for all services of %s" % hostname)
    search_filter = [ 'HOST_NAME|=|%s' % hostname ]
    search_columns = [ 'SERVICE_NAME' ]
    services = icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
    if services is not None:
        svcs = [service['SERVICE_NAME'] for service in services]
        return svcs
    return None

def get_service_status(hostname,service):
    log.debug("Searching for state of service %s of %s" % (service, hostname))
    search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_NAME|=|%s' % service ]
    search_columns = [ 'SERVICE_CURRENT_STATE' ]
    service_state = icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
    if service_state is not None:
        try:
            statenr = [sstate['SERVICE_CURRENT_STATE'] for sstate in service_state]
            state = icinga.translate_state(statenr[0])
            return state
        except:
            log.warning("Something is wrong with the Icinga API.")
            return None
    return None

def get_ok_services(hostname):
    log.debug("Searching for services of %s with an OK state" % hostname)
    search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|=|0', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
    search_columns = [ 'SERVICE_NAME' ]
    ok_services = icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
    if ok_services is not None:
        try:
            ok = [service['SERVICE_NAME'] for service in ok_services]
            return ok
        except:
            log.warning("Something is wrong with the Icinga API.")
            return None
    return None

def get_nok_services(hostname, excluded_services=[]):
    log.debug("Searching for services of %s with a NOK state" % hostname)
    search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|!=|0', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
    search_columns = [ 'SERVICE_NAME' ]
    for service in excluded_services:
        search_filter.append("SERVICE_NAME|!=|%s")
    nok_services = icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
    if nok_services is not None:
        try:
            nok = [service['SERVICE_NAME'] for service in nok_services]
            return nok;
        except:
            log.warning("Something is wrong with the Icinga API.")
            return None
    return None

def get_all_nok_services(hostname, excluded_services=[]):
    log.debug("Searching for ALL services of %s with a NOK state" % hostname)
    search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|!=|0' ]
    search_columns = [ 'SERVICE_NAME' ]
    for service in excluded_services:
        search_filter.append("SERVICE_NAME|!=|%s")
    nok_services = icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
    if nok_services is not None:
        try:
            nok = [service['SERVICE_NAME'] for service in nok_services]
            return nok;
        except:
            log.warning("Something is wrong with the Icinga API.")
            return None
    return None

# FUNCTIONS TO CONTROL CHECKS
def set_checks(hostname, services, state):
    if state == "enable":
        check_state = "ENABLE"
    elif state == "disable":
        check_state = "DISABLE"

    log.info("Setting checks of %s on %s to %s" % (services, hostname, check_state))
    cmdlist = []
    if "host" in services:
        services.remove("host")
        icinga_cmd(hostname, ["%s_HOST_CHECK" % check_state], ["host"])

    cmdlist.append("%s_SVC_CHECK" % check_state)
    return icinga_cmd(hostname, cmdlist, services)

def enable_all_checks(hostname):
    services = get_services(hostname)
    services.append("host")
    return set_checks(hostname, services, "enable")

def disable_all_checks(hostname):
    services = get_services(hostname)
    services.append("host")
    return set_checks(hostname, services, "disable")

def enable_service_check(hostname, service):
    return set_checks(hostname, [service], "enable")

def disable_service_check(hostname, service):
    return set_checks(hostname, [service], "disable")

# FUNCTIONS TO CONRTOL NOTIFICATIONS
def set_notifications(hostname, services, state):
    if state == "enable":
        notification_state = "ENABLE"
    elif state == "disable":
        notification_state = "DISABLE"

    log.info("Setting notifications of %s on %s to %s" % (services, hostname, notification_state))
    cmdlist = []
    if "host" in services:
        services.remove("host")
        icinga_cmd(hostname, ["%s_HOST_NOTIFICATIONS" % notification_state], ["host"])

    cmdlist.append("%s_SVC_NOTIFICATIONS" % notification_state)
    return icinga_cmd(hostname, cmdlist, services)

def disable_all_notifications(hostname):
    services = get_services(hostname)
    services.append("host")
    return set_notifications(hostname, services, "disable")

def enable_all_notifications(hostname):
    services = get_services(hostname)
    services.append("host")
    return set_notifications(hostname, services, "enable")

def disable_service_notifications(hostname, service):
    return set_notifications(hostname, [service], "disable")

def enable_service_notifications(hostname, service):
    return set_notifications(hostname, [service], "enable")

# FUNCTION TO SCHEDULE CHECKS
def schedule_check(hostname, services=None, forced=None):
    log.info("Scheduling check of %s on %s" % (services, hostname))
    schedule = "SCHEDULE"
    cmdlist = []
    targetlist = {}
    targetlist["checktime"] = "%s" % current_time

    if forced == "force":
        log.info("Forcing check")
        schedule = "SCHEDULE_FORCED"

    if "host" in services:
        services.remove("host")
        icinga_cmd(hostname, ["%s_HOST_CHECK" % schedule], ["host"], targetlist) 

    cmdlist.append("%s_SVC_CHECK" % schedule)
    return icinga_cmd(hostname, cmdlist, services, targetlist)

def schedule_check_all_services(hostname):
    servicelist=[]
    for s in get_services(hostname): servicelist.append(s)
    return schedule_check(hostname, servicelist, "force")

def acknowledge_problem(hostname, services, author="nobody", comment="No comment specified", sticky=2, notify=0, persistent=1):
    log.info("Acknowlediging %s on %s" % (services, hostname))
    cmdlist = []
    targetlist = {}
    targetlist["host"] = hostname
    targetlist["sticky"] = sticky
    targetlist["notify"] = notify
    targetlist["persistent"] = persistent
    targetlist["author"] = author
    targetlist["comment"] = comment

    if "host" in services:
        services.remove("host")
        icinga_cmd(hostname, ["ACKNOWLEDGE_HOST_PROBLEM"], ["host"], targetlist)

    cmdlist.append("ACKNOWLEDGE_SVC_PROBLEM")
    return icinga_cmd(hostname, cmdlist, services, targetlist)

def remove_acknowledgement(hostname, services):
    log.info("Removing acknowledgement and comments of %s on %s" % (services, hostname))
    cmdlist = []

    if "host" in services:
        services.remove("host")
        icinga_cmd(hostname, ["REMOVE_HOST_ACKNOWLEDGEMENT"], ["host"])

    cmdlist.append("REMOVE_SVC_ACKNOWLEDGEMENT")
    return icinga_cmd(hostname, cmdlist, services)

