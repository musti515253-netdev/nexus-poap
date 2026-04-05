#!/usr/bin/env python
##############################################################
# POAP Script for Cisco Nexus 3K
# Server: Red Hat Linux
# NX-OS Python 2.7
##############################################################

import os, sys, signal, syslog

TFTP_SERVER = "192.168.1.100"       # Red Hat Server IP
CONFIG_FILE = "switch_config.cfg"
LOG_FILE    = "/bootflash/poap.log"

##############################################################
# Logger — writes to syslog, bootflash log, and console
##############################################################
def log(msg):
    message = "POAP: " + str(msg)
    try:
        syslog.syslog(9, message)
    except:
        pass
    try:
        with open(LOG_FILE, "a") as f:
            f.write(message + "\n")
    except:
        pass
    print(message)

##############################################################
# Timeout handler — NX-OS sends SIGTERM if POAP takes too long
##############################################################
def sigterm_handler(signum, frame):
    log("SIGTERM - POAP timed out!")
    sys.exit(1)

signal.signal(signal.SIGTERM, sigterm_handler)

##############################################################
# CLI runner — 3 fallback methods for all NX-OS versions
##############################################################
def run_cli(cmd):
    log("Running: " + cmd)

    # Method 1 — works on most NX-OS versions
    try:
        import cli
        return str(cli.cli(cmd))
    except:
        pass

    # Method 2 — older NX-OS versions
    try:
        import cisco
        return str(cisco.cli(cmd))
    except:
        pass

    # Method 3 — universal fallback via vsh subprocess
    try:
        import subprocess
        return subprocess.check_output(
            ["vsh", "-c", cmd],
            stderr=subprocess.STDOUT)
    except Exception as e:
        log("All CLI methods failed: " + str(e))

    return ""

##############################################################
# TFTP downloader — tries with vrf management first, then without
##############################################################
def tftp_get(filename, destination):
    # Try with vrf management
    cmd = "copy tftp://{}/{} {} vrf management".format(
          TFTP_SERVER, filename, destination)
    run_cli(cmd)

    if filename in str(run_cli("dir bootflash:/")):
        log("Confirmed on bootflash: " + filename)
        return True

    # Try without vrf
    cmd2 = "copy tftp://{}/{} {}".format(
           TFTP_SERVER, filename, destination)
    run_cli(cmd2)

    if filename in str(run_cli("dir bootflash:/")):
        log("Confirmed on bootflash: " + filename)
        return True

    log("ERROR: File not found after download: " + filename)
    return False

##############################################################
# Apply config to startup-config
##############################################################
def apply_config(path):
    run_cli("copy {} startup-config".format(path))
    verify = run_cli("show startup-config")
    return verify and len(str(verify)) > 10

##############################################################
# MAIN
##############################################################
def main():
    log("=" * 50)
    log("POAP Script Started")
    log("TFTP Server : " + TFTP_SERVER)
    log("Config File : " + CONFIG_FILE)
    log("=" * 50)

    dest = "bootflash:/" + CONFIG_FILE

    # Step 1 — Download config
    log("STEP 1: Downloading config from TFTP server...")
    if not tftp_get(CONFIG_FILE, dest):
        log("FATAL: Config download failed!")
        log("Check: Is switch_config.cfg in /var/lib/tftpboot/?")
        sys.exit(1)
    log("STEP 1: Config downloaded successfully!")

    # Step 2 — Apply config
    log("STEP 2: Applying config to startup-config...")
    if not apply_config(dest):
        log("FATAL: Config apply failed!")
        sys.exit(1)
    log("STEP 2: Config applied successfully!")

    log("=" * 50)
    log("POAP COMPLETED SUCCESSFULLY!")
    log("=" * 50)

if __name__ == "__main__":
    main()
