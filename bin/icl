#!/usr/bin/env python
'''
@author: Jeffrey Lensen | Hyves
'''

import os
import sys
import optparse
import time
import socket
import urllib
import simplejson
import logging

import icinga
from icinga import api
from icinga import livestatus
from icinga import set_loglevel

log = logging.getLogger("icinga.icl")

def setupOptions(parser):
    parser.add_option("--system", "-s", "--host",
        action="append",
        dest="system",
        metavar="HOSTNAME[,HOSTNAME]",
        help="Selects the host with this name")
    parser.add_option("--function", "-f", "--hostgroup",
        action="append",
        dest="function",
        metavar="HOSTGROUPNAME[,HOSTGROUPNAME]",
        help="Selects all hosts in the hostgroup with this name")
    parser.add_option("--service",
        action="append",
        dest="service",
        metavar="[<service name>/host]",
        help="Specifies the service to which an action should be performed. When not specified, all services will be selected")
    parser.add_option("--action", "-a",
        action="append",
        dest="action",
        metavar="<action>",
        help="Action to be performed on specified service/host:     \
        - status (default):                Show status info         \
        - check:                           Perform a check          \
        - alerts-off (off):                Turn alerts off          \
        - alerts-on (on):                  Turn alerts on           \
        - checks-off:                      Turn checks off          \
        - checks-on:                       Turn checks on           \
        - acknowledge (ack):               Acknowledge problem      \
        - remove-acknowledgement (remove-ack): Remove an ack")
    parser.add_option("--force",
        action="store_true",
        dest="force",
        help="Force the check of the specified service/host     (Note: this will also force a check of passive checks!")
    parser.add_option("--openproblems",
        action="store_true",
        dest="openproblems",
        help="Shows you all open problems")
    parser.add_option("--allproblems",
        action="store_true",
        dest="allproblems",
        help="Shows you all problems")
    parser.add_option("--loglevel", "-l",
        action="store",
        default="INFO",
        dest="loglevel",
        help="loglevel for the script, defaults to INFO")
    parser.add_option("--silence",
        action="store_true",
        dest="silence",
        help="Globally turns off notifications on all instances")
    parser.add_option("--noise",
        action="store_true",
        dest="noise",
        help="Globally turns on notifications on all instances")

    return parser

def _validate(options, args):
    if options.system is None and options.function is None and options.silence is None and options.noise is None and options.openproblems is None and options.allproblems is None:
        log.fatal("No systems to select")
        return False
    return True

def main():
    parser = optparse.OptionParser()
    parser.disable_interspersed_args()
    setupOptions(parser)
    (options, args) = parser.parse_args()
    log.setLevel(icinga.get_loglevel(options.loglevel))
    icinga.set_loglevel(options.loglevel)

    now = time.time()

    if not _validate(options, args):
        parser.print_help()
        return 1

    hostlist = []
    if options.system != [] and options.system is not None:
        for i in options.system: hostlist.extend(i.split(','))

    if options.function != [] and options.function is not None:
        for i in options.function: options.function.extend(i.split(',')); options.function.remove(i);
        for function in options.function:
            host_searchcolumns = [ 'HOST_NAME' ]
            host_searchfilter = [ 'HOSTGROUP_NAME|=|%s' % function ]
            host_searchoutput = api.icinga_search("host", host_searchfilter, host_searchcolumns, "HOST_NAME")
            for result in host_searchoutput:
                try:
                    hostlist.append(result['HOST_NAME'])
                except:
                    log.debug("Could not add host")

    if options.action is None: options.action=["status"]

    if options.silence is not None or options.noise is not None:
#       use this for >= 1.6
        instance_list = api.icinga_search("instance", [], ['INSTANCE_NAME'], "INSTANCE_NAME")
#       use this for < 1.6
#        instance_list = api.icinga_search("host", [], ['INSTANCE_NAME'], "INSTANCE_NAME")
        if options.silence:
            action = "DISABLE"
        if options.noise:
            action = "ENABLE"
        for instance in instance_list:
            log.info("Setting global notifications on %s to %s" % (instance['INSTANCE_NAME'], action))
            livestatus.icinga_cmd(None, ["%s_NOTIFICATIONS" % action], instance['INSTANCE_NAME'])

    if options.allproblems is not None or options.openproblems is not None:
        if options.openproblems is not None:
            log.info("Open Problems")
            host_searchfilter = [ 'HOST_NOTIFICATIONS_ENABLED|=|1', 'HOST_CURRENT_STATE|!=|0', 'HOST_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
            service_searchfilter = [ 'SERVICE_NOTIFICATIONS_ENABLED|=|1', 'HOST_NOTIFICATIONS_ENABLED|=|1', 'SERVICE_CURRENT_STATE|!=|0', 'HOST_CURRENT_STATE|=|0', 'HOST_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED|=|0' ]
        if options.allproblems is not None:
            log.info("All Problems")
            host_searchfilter = [ 'HOST_CURRENT_STATE|!=|0' ]
            service_searchfilter = [ 'SERVICE_CURRENT_STATE|!=|0', 'HOST_CURRENT_STATE|=|0' ]

        host_searchcolumns = [ 'HOST_NAME', 'HOST_CURRENT_STATE', 'HOST_CURRENT_CHECK_ATTEMPT', 'HOST_MAX_CHECK_ATTEMPTS', 'HOST_OUTPUT' ]
        log.info("Host problems")
        print "\033[01;33m%-42s %-15s %-10s %s\033[0m" % ("Hostname", "State", "Attempt", "Output")
        allopenhostprobs = []
        openhostprobs = api.icinga_search("host", host_searchfilter, host_searchcolumns, "HOST_NAME")
        if openhostprobs is not None:
            for prob in openhostprobs:
                allopenhostprobs.append(prob)
        sorted_hostprobs = sorted(allopenhostprobs)
        for prob in sorted_hostprobs:
            print "* %-40s %-15s %s/%-8s %s" % (prob['HOST_NAME'], icinga.translate_state(prob['HOST_CURRENT_STATE'], "host"), prob['HOST_CURRENT_CHECK_ATTEMPT'], prob['HOST_MAX_CHECK_ATTEMPTS'], prob['HOST_OUTPUT'])

        service_searchcolumns = [ 'HOST_NAME', 'SERVICE_NAME', 'SERVICE_CURRENT_STATE', 'SERVICE_CURRENT_CHECK_ATTEMPT', 'SERVICE_MAX_CHECK_ATTEMPTS', 'SERVICE_OUTPUT' ]
        log.info("Service problems")
        print "\033[01;33m%-42s %-42s %-15s %-10s %s\033[0m" % ("Hostname", "Service", "State", "Attempt", "Output")
        allopenserviceprobs = []
        openserviceprobs = api.icinga_search("service", service_searchfilter, service_searchcolumns, "HOST_NAME;SERVICE_NAME")
        if openserviceprobs is not None:
            for prob in openserviceprobs:
                allopenserviceprobs.append(prob)
        sorted_serviceprobs = sorted(allopenserviceprobs)
        for prob in sorted_serviceprobs[:]:
            print "* %-40s %-42s %-15s %s/%-8s %s" % (prob['HOST_NAME'], prob['SERVICE_NAME'], icinga.translate_state(prob['SERVICE_CURRENT_STATE'], "service"), prob['SERVICE_CURRENT_CHECK_ATTEMPT'], prob['SERVICE_MAX_CHECK_ATTEMPTS'], prob['SERVICE_OUTPUT'])

    for host in hostlist:
        servicelist = []
        if options.service == [] or options.service is None or options.service == "all":
            for s in api.get_services(host): servicelist.append(s)
            servicelist.insert(0,"host")
        else:
            for i in options.service: servicelist.extend(i.split(','))

        instance_output = api.icinga_search("host", ["HOST_NAME|=|%s" % host], ['INSTANCE_NAME'], "INSTANCE_NAME")

        try:
            instance_name = instance_output[0]['INSTANCE_NAME']
            log.info("%s is monitored by %s" % (host, instance_name))
        except:
            log.warning("No monitoring instance found for %s" % host)

        if options.force: force = "force"
        else: force = ""

        actiondict = {
                "status":       lambda: action_status(host,servicelist),
                "check":        lambda: action_check(host,servicelist,force),
                "alerts-off":   lambda: action_alertsoff(host,servicelist),
                "off":          lambda: action_alertsoff(host,servicelist),
                "alerts-on":    lambda: action_alertson(host,servicelist),
                "on":           lambda: action_alertson(host,servicelist),
                "checks-off":   lambda: action_checksoff(host,servicelist),
                "checks-on":    lambda: action_checkson(host,servicelist),
                "acknowledge":  lambda: action_ack(host,servicelist),
                "ack":          lambda: action_ack(host,servicelist),
                "remove-acknowledgement": lambda: action_removeack(host,servicelist),
                "remove-ack":   lambda: action_removeack(host,servicelist)
        }

        for action in options.action:
            log.debug("Performing action %s" % action)
            actiondict[action]()


def action_status(host,servicelist):
    hostname = host.split(".")[0]

    # Print header
    print "\033[01;33m%-43s %-10s %-15s %-15s %-15s %-10s %s\033[0m" % ("Service", "Status", "Notifications", "Active Checks", "Acknowledged", "Attempt", "Output")

    host_searchcolumns = [ 'HOST_NAME', 'HOST_CURRENT_STATE', 'HOST_NOTIFICATIONS_ENABLED', 'HOST_ACTIVE_CHECKS_ENABLED', 'HOST_PROBLEM_HAS_BEEN_ACKNOWLEDGED', 'HOST_CURRENT_CHECK_ATTEMPT', 'HOST_MAX_CHECK_ATTEMPTS', 'HOST_OUTPUT' ]
    service_searchcolumns = [ 'SERVICE_NAME', 'SERVICE_CURRENT_STATE', 'SERVICE_NOTIFICATIONS_ENABLED', 'SERVICE_ACTIVE_CHECKS_ENABLED', 'SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED', 'SERVICE_CURRENT_CHECK_ATTEMPT', 'SERVICE_MAX_CHECK_ATTEMPTS', 'SERVICE_OUTPUT' ]

    # Get and print service status information of all specified services
    status_get_filter = ["HOST_NAME|=|%s" % host]
    service_filter = []
    for status_service in servicelist:
        if status_service == "host":
            hoststatus_output = api.icinga_search("host", status_get_filter, host_searchcolumns, "HOST_NAME")
            try:
                print "* %-41s %-10s %-15s %-15s %-15s %s/%-8s %s" % (
                        hoststatus_output[0]['HOST_NAME'],
                        icinga.translate_state(hoststatus_output[0]['HOST_CURRENT_STATE'], "host"),
                        icinga.translate_enabled(hoststatus_output[0]['HOST_NOTIFICATIONS_ENABLED']),
                        icinga.translate_enabled(hoststatus_output[0]['HOST_ACTIVE_CHECKS_ENABLED']),
                        icinga.translate_enabled(hoststatus_output[0]['HOST_PROBLEM_HAS_BEEN_ACKNOWLEDGED']),
                        hoststatus_output[0]['HOST_CURRENT_CHECK_ATTEMPT'],
                        hoststatus_output[0]['HOST_MAX_CHECK_ATTEMPTS'],
                        hoststatus_output[0]['HOST_OUTPUT'])
            except:
                print "* There was a problem retrieving data from the API"

            if status_service == "host":
                continue

        if status_service != "host":
            service_filter.append("SERVICE_NAME|=|%s" % status_service)

    if len(service_filter) > 0:
        service_get_filter = "OR(%s)" % ";".join(service_filter)
        status_get_filter.append(service_get_filter)

        servicestatus_output = api.icinga_search("service", status_get_filter, service_searchcolumns, "SERVICE_NAME")
        if servicestatus_output is not None:
            for servicestatus in servicestatus_output:
                try:
                    print "* %-41s %-10s %-15s %-15s %-15s %s/%-8s %s" % (
                        servicestatus['SERVICE_NAME'],
                        icinga.translate_state(servicestatus['SERVICE_CURRENT_STATE'], "service"),
                        icinga.translate_enabled(servicestatus['SERVICE_NOTIFICATIONS_ENABLED']),
                        icinga.translate_enabled(servicestatus['SERVICE_ACTIVE_CHECKS_ENABLED']),
                        icinga.translate_enabled(servicestatus['SERVICE_PROBLEM_HAS_BEEN_ACKNOWLEDGED']),
                        servicestatus['SERVICE_CURRENT_CHECK_ATTEMPT'],
                        servicestatus['SERVICE_MAX_CHECK_ATTEMPTS'],
                        servicestatus['SERVICE_OUTPUT'] )
                except:
                    print "* There was a problem retrieving data from the API"

def action_check(host,servicelist,force):
    api.schedule_check(host, servicelist, force)

def action_alertson(host,servicelist):
    api.set_notifications(host, servicelist, "enable")

def action_alertsoff(host,servicelist):
    api.set_notifications(host, servicelist, "disable")

def action_checkson(host,servicelist):
    api.set_checks(host, servicelist, "enable")

def action_checksoff(host,servicelist):
    api.set_checks(host, servicelist, "disable")

def action_ack(host,servicelist):
    author = os.environ.get("USER")
    comment = "Acknowledged by %s with icl" % author
    for service in servicelist:
        api.acknowledge_problem(host, [service], author, comment)

def action_removeack(host,servicelist):
    for service in servicelist:
        api.remove_acknowledgement(host, [service])

if __name__ == "__main__":
    sys.exit(main())

