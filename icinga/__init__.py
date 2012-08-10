import os
import sys
import logging
import ConfigParser

log = logging.getLogger(__name__)
logformat="%(name)s -> %(message)s"
loglevel=logging.INFO
logging.basicConfig(format=logformat)
log.setLevel(loglevel)

def get_loglevel(level):
    _levelNames = {
        "CRITICAL" : logging.CRITICAL,
        "FATAL" : logging.FATAL,
        "ERROR" : logging.ERROR,
        "WARNING" : logging.WARNING,
        "WARN" : logging.WARN,
        "INFO" : logging.INFO,
        "DEBUG" : logging.DEBUG,
        "NOTSET" : logging.NOTSET
    }
    try:
        loglevel = _levelNames[level]
    except KeyError, e:
        loglevel = logging.INFO
    return loglevel


def set_loglevel(level):
    loglevel = get_loglevel(level)
    log.setLevel(loglevel)

def translate_state(statenr, checktype="service"):
    if checktype == "service":
        service_state_map = {
            0: "OK", "0": "OK", "OK": 0,
            1: "WARNING", "1": "WARNING", "WARNING": 1,
            2: "CRITICAL", "2": "CRITICAL", "CRITICAL": 2,
            3: "UNKNOWN", "3": "UNKNOWN", "UNKNOWN": 3,
        }
        state = service_state_map.get(statenr)
    elif checktype == "host":
        host_state_map = {
            0: "UP", "0": "UP",
            1: "DOWN", "1": "DOWN",
            2: "DOWN", "2": "DOWN",
            3: "DOWN", "3": "DOWN",
        }
        state = host_state_map.get(statenr)
    elif checktype == "monitoring":
        monitoring_state_map = {
            0: "INACTIVE", "0": "INACTIVE",
            1: "ACTIVE", "1": "ACTIVE",
        }
        state = monitoring_state_map.get(statenr)
    return state

def translate_enabled(enablednr):
    enabled_map = {
        0: "No", "0": "No",
        1: "Yes", "1": "Yes",
    }
    enabled = enabled_map.get(enablednr)
    return enabled

def exit_warning(mesg):
    log.debug("Exit with WARNING")
    print mesg
    sys.exit(translate_state("WARNING"))

def exit_critical(mesg):
    log.debug("Exit with CRITICAL")
    print mesg
    sys.exit(translate_state("CRITICAL"))

def exit_ok(mesg):
    log.debug("Exit with OK")
    print mesg
    sys.exit(translate_state("OK"))

def exit_unknown(mesg):
    log.debug("Exit with UNKNOWN")
    print mesg
    sys.exit(translate_state("UNKNOWN"))

def parse_configfile(sectionlist=[]):
    configlocations = [ os.path.expanduser("~/.icinga/icl.cfg"), "/etc/icinga/icl.cfg" ]

    config = ConfigParser.RawConfigParser()
    log.debug("Trying to load configfiles: %s" % configlocations)
    ConfigFiles_InUse = config.read(configlocations)
    log.debug("Loaded configfiles: %s" % ConfigFiles_InUse)

    myconfig = {}
    for section in sectionlist:
        try:
            myconfig[section] = dict(config.items(section))
            log.debug("Values in section %s are: %s", section, myconfig[section])
        except ConfigParser.NoSectionError, exc:
            log.debug("Can't find section %s in %s", exc.section, ConfigFiles_InUse)
            raise ConfigFileError("Missing mandatory section(s) %s in configfile(s) %s" % (exc.section, ConfigFiles_InUse))
    return myconfig

