'''
Created on Oct 25, 2010

@author: jeffrey lensen

'''

from smdb2.v1.model import system, status
import icinga
import os
import sys
import socket
import time
import simplejson
import urllib
import logging

log = logging.getLogger(__name__)
current_time = time.time()

def send_to_icinga(instancehost, cmd):
    instanceport = 6557
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#    s.setblocking(0)
    s.settimeout(2.0)
    try:
        s.connect((instancehost, instanceport))
    except socket.error, msg:
        log.warning("Failed to connect to %s on port %s: %s" % (instancehost, instanceport, msg))
        return None

    try:
        # Write command to socket
        log.debug("Sending command to %s:\n%s" % (instancehost, cmd))
        s.send(cmd+'\n')
        # Important: Close sending direction. That way
        # the other side knows, we are finished.
        s.shutdown(socket.SHUT_WR)
        # Now read the answer. We need to do a while loop because sometimes the data is too large
        total_data=[]
        while True:
            data = s.recv(8192)
            if not data:
                break
            total_data.append(data)
        answer = ''.join(total_data)

        log.debug("Output:\n%s" % answer)
    except socket.error, msg:
        s.close()
        log.warning("Failed to send cmd to %s" % instancehost)
        log.debug("Command: %s" % cmd.rstrip('\n'))
        log.debug("Exception: %s" % msg)
        return None

    s.close()
    try:
        log.debug("Returning simplejson.loads(%s)" % answer)
        return simplejson.loads(answer)
    except:
        log.debug("Could not load simplejson object. Returning None")
        return None

def icinga_cmd(hostname=None, commands=None, instancehost=None):
    if hostname is not None:
        log.debug("No instancehost specified, searching for one")
        instancehost = get_monitoring_host(hostname)
    if instancehost is None:
        log.warning("Skipping because no monitoring host was selected")
        return
    cmd_list = []
    for command in commands:
        cmd_list.append("COMMAND [%d] %s" % (current_time, command))
    cmd = '\n'.join(cmd_list)
    cmd_output = send_to_icinga(instancehost, cmd)
    log.debug("icinga_cmd output: %s" % cmd_output)
    return cmd_output

def icinga_get(hostname=None, gettype=None, withcolumns=None, withfilter=None, withoutput=None, instancehost=None):
    if hostname is not None and instancehost is None:
        instancehost = get_monitoring_host(hostname)
    if instancehost is None:
        log.warning("Skipping because no monitoring host for %s was found" % hostname)
        return
    cmd_list = []
    cmd_list.append('GET %s' % gettype)
    if withcolumns is not None:
        cmd_list.append('Columns: %s' % withcolumns)
    if withfilter is not None:
        for searchfilter in withfilter:
            cmd_list.append('Filter: %s' % searchfilter)
    if withoutput is not None:
        cmd_list.append('OutputFormat: %s' % withoutput)
    else:
        cmd_list.append('OutputFormat: json')

    cmd = '\n'.join(cmd_list)
    cmd_output = send_to_icinga(instancehost, cmd)
    if cmd_output is not None and cmd_output != []:
        sorted_output = sorted(cmd_output)
    log.debug("icinga_get output: %s" % cmd_output)
    return cmd_output

def get_monitoring_host(hostname):
    instanceport = 6557
    instancelist = []

    s = system.get_list_by_functiondescription("icinga_core", status.convert_string_to_statusid("Operational"))
    if s:
        instancelist.extend(s)

    cmd_list = []
    cmd_list.append('GET hosts')
    cmd_list.append('Columns: host_name')
    cmd_list.append('Filter: host_name = %s' % hostname)
    cmd_list.append('OutputFormat: json')
    cmd = '\n'.join(cmd_list)

    for instance in instancelist[:]:
        instancehost = instance.name
        log.debug("searching for %s on %s" % (hostname, instancehost))
        cmd_output = send_to_icinga(instancehost, cmd)
        if cmd_output is not None and cmd_output != []:
            if cmd_output[0][0] == hostname:
                log.debug("%s is monitored by %s" % (hostname, instancehost))
                return instancehost
    log.warning("Could not determine monitoring host for %s" % hostname)
    return None

def get_services(hostname):
    log.debug("Searching for all services of %s" % hostname)
    services = icinga_get(hostname,"services","service_description",["host_name = %s" % hostname]);
    if services is not None:
        svcs = [service[0] for service in services]
        return svcs
    return None

def get_service_status(hostname,service):
    log.debug("Searching for state of service %s of %s" % (service, hostname))
    service_state = icinga_get(hostname,"services","state",["host_name = %s" % hostname,"description = %s" % service]);
    if service_state is not None:
        statenr = [sstate[0] for sstate in service_state]
        state = icinga.translate_state(statenr[0])
        return state
    return None


def get_ok_services(hostname):
    log.debug("Searching for services of %s with an OK state" % hostname)
    ok_services = icinga_get(hostname,"services","service_description",["host_name = %s" % hostname,"state = 0","acknowledged = 0"]);
    if ok_services is not None:
        ok = [service[0] for service in ok_services]
        return ok
    return None

def get_nok_services(hostname, excluded_services=[]):
    log.debug("Searching for services of %s with a NOK state" % hostname)
    search_filter = ["host_name = %s" % hostname, "state != 0", "acknowledged = 0"]
    for service in excluded_services:
        search_filter.append("service_description != %s" % service)
    nok_services = icinga_get(hostname,"services","service_description",search_filter)
    if nok_services is not None:
        nok = [service[0] for service in nok_services]
        return nok
    return None

def get_all_nok_services(hostname, excluded_services=[]):
    log.debug("Searching for ALL services of %s with a NOK state" % hostname)
    search_filter = ["host_name = %s" % hostname, "state != 0"]
    for service in excluded_services:
        search_filter.append("service_description != %s" % service)
    nok_services = icinga_get(hostname,"services","service_description",search_filter)
    if nok_services is not None:
        nok = [service[0] for service in nok_services]
        return nok
    return None


# FUNCTIONS TO CONTROL CHECKS
def set_checks(hostname, service, state):
    action_cmd = []
    if state == "enable":
        check_state = "ENABLE"
    elif state == "disable":
        check_state = "DISABLE"
    if service == "host":
        action_cmd.append("%s_HOST_CHECK;%s" % (check_state, hostname))
    elif service == "all":
        action_cmd.append("%s_HOST_SVC_CHECKS;%s" % (check_state, hostname))
        action_cmd.append("%s_HOST_CHECK;%s" % (check_state, hostname))
    else:
        action_cmd.append("%s_SVC_CHECK;%s;%s" % (check_state, hostname, service))
    log.info("Setting checks of %s on %s to %s" % (service, hostname, check_state))
    return icinga_cmd(hostname, action_cmd)

def enable_all_checks(hostname):
    return set_checks(hostname, "all", "enable")

def disable_all_checks(hostname):
    return set_checks(hostname, "all", "disable")

def enable_service_check(hostname, service):
    return set_checks(hostname, service, "enable")

def disable_service_check(hostname, service):
    return set_checks(hostname, service, "disable")

# FUNCTIONS TO CONRTOL NOTIFICATIONS
def set_notifications(hostname, service, state):
    action_cmd = []
    if state == "enable":
        notification_state = "ENABLE"
    elif state == "disable":
        notification_state = "DISABLE"
    if service == "host":
        action_cmd.append("%s_HOST_NOTIFICATIONS;%s" % (notification_state, hostname))
    elif service == "all":
        action_cmd.append("%s_HOST_SVC_NOTIFICATIONS;%s" % (notification_state, hostname))
        action_cmd.append("%s_HOST_NOTIFICATIONS;%s" % (notification_state, hostname))
    else:
        action_cmd.append("%s_SVC_NOTIFICATIONS;%s;%s" % (notification_state, hostname, service))
    log.info("Setting notifications of %s on %s to %s" % (service, hostname, notification_state))
    return icinga_cmd(hostname, action_cmd)

def disable_all_notifications(hostname):
    return set_notifications(hostname, "all", "disable")

def enable_all_notifications(hostname):
    return set_notifications(hostname, "all", "enable")

def disable_service_notifications(hostname, service):
    return set_notifications(hostname, service, "disable")

def enable_service_notifications(hostname, service):
    return set_notifications(hostname, service, "enable")

# FUNCTION TO SCHEDULE CHECKS
def schedule_check(hostname, service, forced=None):
    log.info("Scheduling check of %s on %s" % (service, hostname))
    action_cmd = []
    if service == "host":
        type = "HOST_CHECK"
        svc = hostname
    elif service == "all":
        type = "HOST_SVC_CHECKS"
        svc = hostname
    else:
        type = "SVC_CHECK"
        svc = "%s;%s" % (hostname, service)
    if forced == "force":
        log.info("Forcing check")
        type = "FORCED_%s" % type
    action_cmd.append("SCHEDULE_%s;%s;%d" % (type, svc, current_time))
    return icinga_cmd(hostname, action_cmd)

def acknowledge_problem(hostname, service, author="nobody", comment="No comment specified", sticky=2, notify=0, persistent=1):
    log.info("Acknowlediging %s on %s" % (service, hostname))
    action_cmd = []
    ack_string = "%d;%d;%d;%s;%s" % (sticky, notify, persistent, author, comment)
    if service == "host":
        action_cmd.append("ACKNOWLEDGE_HOST_PROBLEM;%s;%s" % (hostname, ack_string))
    elif service == "all":
        action_cmd.append("ACKNOWLEDGE_HOST_PROBLEM;%s;%s" % (hostname, ack_string))
        all_services = get_services(hostname)
        if all_services:
            for svc in all_services:
                action_cmd.append("ACKNOWLEDGE_SVC_PROBLEM;%s;%s;%s" % (hostname, svc, ack_string))
    else:
        action_cmd.append("ACKNOWLEDGE_SVC_PROBLEM;%s;%s;%s" % (hostname, service, ack_string))
    return icinga_cmd(hostname, action_cmd)

def remove_acknowledgement(hostname, service):
    log.info("Removing acknowledgement and comments of %s on %s" % (service, hostname))
    action_cmd = []
    if service == "host":
        action_cmd.append("REMOVE_HOST_ACKNOWLEDGEMENT;%s" % hostname)
        action_cmd.append("DEL_ALL_HOST_COMMENTS;%s" % hostname)
    elif service == "all":
        action_cmd.append("REMOVE_HOST_ACKNOWLEDGEMENT;%s" % hostname)
        action_cmd.append("DEL_ALL_HOST_COMMENTS;%s" % hostname)
        all_services = get_services(hostname)
        if all_services:
            for svc in all_services:
                action_cmd.append("REMOVE_SVC_ACKNOWLEDGEMENT;%s;%s" % (hostname, svc))
                action_cmd.append("DEL_ALL_SVC_COMMENTS;%s;%s" % (hostname, svc))
    else:
        action_cmd.append("REMOVE_SVC_ACKNOWLEDGEMENT;%s;%s" % (hostname, service))
        action_cmd.append("DEL_ALL_SVC_COMMENTS;%s;%s" % (hostname, service))
    return icinga_cmd(hostname, action_cmd)

