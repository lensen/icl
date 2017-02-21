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
import ConfigParser

import icinga

log = logging.getLogger(__name__)
current_time = strftime("%Y-%m-%d %H:%M:%S")

class API:

    def __init__(self, sectionname="icinga"):
        sectionlist = [sectionname]
        configlocations = [ os.path.expanduser("~/.icinga/icl.cfg"), "/etc/icinga/icl.cfg" ]

        config = ConfigParser.RawConfigParser()
        log.debug("Trying to load configfiles: %s" % configlocations)
        ConfigFiles_InUse = config.read(configlocations)
        log.debug("Loaded configfiles: %s" % ConfigFiles_InUse)

        __config = {}
        for section in sectionlist:
            try:
                __config[section] = dict(config.items(section))
                log.debug("Values in section %s are: %s", section, __config[section])
            except ConfigParser.NoSectionError, exc:
                log.critical("Can't find section %s in %s", exc.section, ConfigFiles_InUse)
                sys.exit(1)

        self.api_app_id = __config[sectionname]["api_app_id"]
        self.api_base_url = __config[sectionname]["api_base_url"]
        self.proxies = simplejson.loads(__config[sectionname]["proxies"])

    def icinga_search(self, searchtype, search_filter, search_columns, search_orderfield, search_orderdirection="ASC"):
        if self.api_app_id == "" or self.api_base_url == "":
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
        authkey='/authkey=' + self.api_app_id
        output='/json'
        args = searchtype + filter + columns + order + authkey + output
        url = self.api_base_url + urllib.quote(args)
        log.debug("Search URL: %s%s" % (self.api_base_url, args))
        try:
            result = simplejson.load(urllib.urlopen(url, proxies=self.proxies))
            log.debug("Search result: %s" % result)
        except ValueError:
            log.error("Failed to run jsonload on result")
            return None
        except IOError, msg:
            log.error("Failed to execute icinga search: %s" % (msg))
            return None
        try:
            return result['result']
        except:
            return None

    def send_to_icinga(self, cmd, target):
        if self.api_app_id == "" or self.api_base_url == "":
            return None
        params = {}
        targetstr = "%s" % target

        socket.setdefaulttimeout(10)
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        params["cmd"] = cmd
        params["target"] = targetstr.replace(' \'', '\'')
        params["data"] = {}
        params["authkey"] = self.api_app_id
        args = "/cmd"
        for param in params:
            args = args + "%s=%s" % (param, params[param])

        url = self.api_base_url + urllib.quote(args.replace('\'', '"'))
        log.debug("CMD URL: %s" % self.api_base_url + args.replace('\'', '"'))

        try:
            response = urllib.urlopen(url, proxies=self.proxies)
            log.debug(response.read())
            return response
        except:
            return None

    def group(self, s, n): return [s[i:i+n] for i in xrange(0, len(s), n)]

    def icinga_cmd(self, hostname=None, cmdlist=None, services=None, targetlist={}):
        targets = []
        if hostname is not None:
            log.debug("Searching for monitoring instance")
            instancehost = self.get_monitoring_host(hostname)
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

            for targetgroup in self.group(targets, 35):
                self.send_to_icinga(cmd, targetgroup)
        return

    def get_monitoring_host(self, hostname):
        icinga_result = self.icinga_search('host', ['HOST_NAME|=|%s' % hostname], ['INSTANCE_NAME'], 'HOST_ID', 'DESC')
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

    def get_services(self, hostname):
        log.debug("Searching for all services of %s" % hostname)
        search_filter = [ 'HOST_NAME|=|%s' % hostname ]
        search_columns = [ 'SERVICE_NAME' ]
        services = self.icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
        if services is not None:
            svcs = [service['SERVICE_NAME'] for service in services]
            return svcs
        return None

    def get_service_status(self, hostname, service):
        log.debug("Searching for state of service %s of %s" % (service, hostname))
        search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_NAME|=|%s' % service ]
        search_columns = [ 'SERVICE_CURRENT_STATE' ]
        service_state = self.icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
        if service_state is not None:
            try:
                statenr = [sstate['SERVICE_CURRENT_STATE'] for sstate in service_state]
                state = icinga.translate_state(statenr[0])
                return state
            except:
                log.warning("Something is wrong with the Icinga API.")
                return None
        return None

    def get_ok_services(self, hostname):
        log.debug("Searching for services of %s with an OK state" % hostname)
        search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|=|0', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
        search_columns = [ 'SERVICE_NAME' ]
        ok_services = self.icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
        if ok_services is not None:
            try:
                ok = [service['SERVICE_NAME'] for service in ok_services]
                return ok
            except:
                log.warning("Something is wrong with the Icinga API.")
                return None
        return None

    def get_nok_services(self, hostname, excluded_services=[]):
        log.debug("Searching for services of %s with a NOK state" % hostname)
        search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|!=|0', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
        search_columns = [ 'SERVICE_NAME' ]
        for service in excluded_services:
            search_filter.append("SERVICE_NAME|!=|%s")
        nok_services = self.icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
        if nok_services is not None:
            try:
                nok = [service['SERVICE_NAME'] for service in nok_services]
                return nok;
            except:
                log.warning("Something is wrong with the Icinga API.")
                return None
        return None

    def get_all_nok_services(self, hostname, excluded_services=[]):
        log.debug("Searching for ALL services of %s with a NOK state" % hostname)
        search_filter = [ 'HOST_NAME|=|%s' % hostname, 'SERVICE_CURRENT_STATE|!=|0' ]
        search_columns = [ 'SERVICE_NAME' ]
        for service in excluded_services:
            search_filter.append("SERVICE_NAME|!=|%s")
        nok_services = self.icinga_search('service', search_filter, search_columns, 'SERVICE_NAME');
        if nok_services is not None:
            try:
                nok = [service['SERVICE_NAME'] for service in nok_services]
                return nok;
            except:
                log.warning("Something is wrong with the Icinga API.")
                return None
        return None

    # FUNCTIONS TO CONTROL CHECKS
    def set_checks(self, hostname, services, state):
        if state == "enable":
            check_state = "ENABLE"
        elif state == "disable":
            check_state = "DISABLE"

        log.info("Setting checks of %s on %s to %s" % (services, hostname, check_state))
        cmdlist = []
        if "host" in services:
            services.remove("host")
            self.icinga_cmd(hostname, ["%s_HOST_CHECK" % check_state], ["host"])

        cmdlist.append("%s_SVC_CHECK" % check_state)
        return self.icinga_cmd(hostname, cmdlist, services)

    def enable_all_checks(self, hostname):
        services = get_services(hostname)
        services.append("host")
        return set_checks(hostname, services, "enable")

    def disable_all_checks(self, hostname):
        services = get_services(hostname)
        services.append("host")
        return set_checks(hostname, services, "disable")

    def enable_service_check(self, hostname, service):
        return set_checks(hostname, [service], "enable")

    def disable_service_check(self, hostname, service):
        return set_checks(hostname, [service], "disable")

    # FUNCTIONS TO CONRTOL NOTIFICATIONS
    def set_notifications(self, hostname, services, state):
        if state == "enable":
            notification_state = "ENABLE"
        elif state == "disable":
            notification_state = "DISABLE"

        log.info("Setting notifications of %s on %s to %s" % (services, hostname, notification_state))
        cmdlist = []
        if "host" in services:
            services.remove("host")
            self.icinga_cmd(hostname, ["%s_HOST_NOTIFICATIONS" % notification_state], ["host"])

        cmdlist.append("%s_SVC_NOTIFICATIONS" % notification_state)
        return self.icinga_cmd(hostname, cmdlist, services)

    def disable_all_notifications(self, hostname):
        services = get_services(hostname)
        services.append("host")
        return set_notifications(hostname, services, "disable")

    def enable_all_notifications(self, hostname):
        services = get_services(hostname)
        services.append("host")
        return set_notifications(hostname, services, "enable")

    def disable_service_notifications(self, hostname, service):
        return set_notifications(hostname, [service], "disable")

    def enable_service_notifications(self, hostname, service):
        return set_notifications(hostname, [service], "enable")

    # FUNCTION TO SCHEDULE CHECKS
    def schedule_check(self, hostname, services=None, forced=None):
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
            self.icinga_cmd(hostname, ["%s_HOST_CHECK" % schedule], ["host"], targetlist) 

        cmdlist.append("%s_SVC_CHECK" % schedule)
        return self.icinga_cmd(hostname, cmdlist, services, targetlist)

    def schedule_check_all_services(self, hostname):
        servicelist=[]
        for s in get_services(hostname): servicelist.append(s)
        return schedule_check(hostname, servicelist, "force")

    def acknowledge_problem(self, hostname, services, author="nobody", comment="No comment specified", sticky=2, notify=0, persistent=1):
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
            self.icinga_cmd(hostname, ["ACKNOWLEDGE_HOST_PROBLEM"], ["host"], targetlist)

        cmdlist.append("ACKNOWLEDGE_SVC_PROBLEM")
        return self.icinga_cmd(hostname, cmdlist, services, targetlist)

    def remove_acknowledgement(self, hostname, services):
        log.info("Removing acknowledgement and comments of %s on %s" % (services, hostname))
        cmdlist = []

        if "host" in services:
            services.remove("host")
            self.icinga_cmd(hostname, ["REMOVE_HOST_ACKNOWLEDGEMENT"], ["host"])

        cmdlist.append("REMOVE_SVC_ACKNOWLEDGEMENT")
        return self.icinga_cmd(hostname, cmdlist, services)

    # INSTANCE WIDE FUNCTIONS
    def set_instance_notifications(self, state):
        cmd = "%s_NOTIFICATIONS" % state
        targets = []
        icinga_result = self.icinga_search('instance', [''], ['INSTANCE_NAME'], 'INSTANCE_NAME', 'ASC')
        if icinga_result is not None and icinga_result != []:
            for result in icinga_result:
                instancetargetlist = {}
                instancetargetlist["instance"] = result['INSTANCE_NAME']
                targets.append(instancetargetlist)

            return self.send_to_icinga(cmd, targets)
        return None

    def disable_instance_notifications(self):
        return self.set_instance_notifications("DISABLE")

    def enable_instance_notifications(self):
        return self.set_instance_notifications("ENABLE")

