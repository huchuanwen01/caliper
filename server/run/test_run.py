#!/usr/bin/env python

import os
import sys
import time
import shutil
import importlib
import types
import string
import re
import logging
import datetime
import subprocess

import socket
import yaml
import threading

try:
    import caliper.common as common
except ImportError:
    import common
from caliper.server.hosts import abstract_ssh
from caliper.server.parser_process import test_perf_tranver as traverse
from caliper.server import crash_handle
from caliper.client.shared import error
from caliper.server import utils as server_utils
from caliper.client.shared import utils
from caliper.client.shared import caliper_path
from caliper.client.shared.settings import settings
from caliper.server.run import write_results
from caliper.client.shared.caliper_path import folder_ope as Folder

class myThread (threading.Thread):
    def __init__(self, threadID, cmd_sec_name, server_run_command, tmp_logfile,
                           kind_bench, server):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.cmd_sec_name = cmd_sec_name
        self.server_run_command = server_run_command
        self.tmp_logfile = tmp_logfile
        self.kind_bench = kind_bench
    	self.server = server

    def run(self):
        client_thread_func(self.cmd_sec_name, self.server_run_command, self.tmp_logfile,
                           self.kind_bench, self.server)

def parse_all_cases( kind_bench, bench_name, run_file,parser_file,dic):
    """
    function: parse one benchmark which was selected in the configuration files
    """
    try:
        # get the abspath, which is filename of run config for the benchmark
        bench_conf_file = os.path.join(caliper_path.config_files.tests_cfg_dir, kind_bench, run_file)
        # get the config sections for the benchmrk
        configRun, sections_run = server_utils.read_config_file(bench_conf_file)
    except AttributeError as e:
        raise AttributeError
    except Exception:
        raise

    logging.debug("the sections to run are: %s" % sections_run)
    if not os.path.exists(Folder.exec_dir):
        os.mkdir(Folder.exec_dir)
    log_bench = os.path.join(Folder.exec_dir, bench_name)
    logfile = log_bench + "_output.log"
    tmp_log_file = log_bench + "_output_tmp.log"
    parser_result_file = log_bench + "_parser.log"
    tmp_parser_file = log_bench + "_parser_tmp.log"
    if os.path.exists(parser_result_file):
        os.remove(parser_result_file)
    #output_logs_names = glob.glob(Folder.exec_dir+"/*output.log")

    # for each command in run config file, read the config for the benchmark
    for i in range(0, len(sections_run)):
        dic[bench_name][sections_run[i]] = {}

        flag = 0
        try:
            category = configRun.get(sections_run[i], 'category')
            scores_way = configRun.get(sections_run[i], 'scores_way')
            parser = configRun.get(sections_run[i], 'parser')
            command = configRun.get(sections_run[i], 'command')
        except Exception:
            logging.debug("no value for the %s" % sections_run[i])
            continue
        if os.path.exists(tmp_parser_file):
            os.remove(tmp_parser_file)
        # parser the result in the tmp_log_file, the result is the output of
        # running the command

        try:
            logging.debug("Parsering the result of command: %s" % command)
            outfp = open(logfile, 'r')
            infp = open(tmp_log_file, 'w')
            infp.write(re.findall("test start\s+%+(.*?)%+\s+test_end", outfp.read(), re.DOTALL)[i])
            infp.close()
            outfp.close()
            parser_result = parser_case(kind_bench, bench_name, parser_file, parser,tmp_log_file, tmp_parser_file)

            dic[bench_name][sections_run[i]]["type"] = type(parser_result)
            dic[bench_name][sections_run[i]]["value"] = parser_result
        except Exception, e:
            logging.info("Error while parsing the result of \" %s \""
                            % sections_run[i])
            logging.info(e)
            if os.path.exists(tmp_parser_file):
                os.remove(tmp_parser_file)
            if os.path.exists(tmp_log_file):
                os.remove(tmp_log_file)
        else:
            server_utils.file_copy(parser_result_file, tmp_parser_file, "a+")
            if os.path.exists(tmp_parser_file):
                os.remove(tmp_parser_file)
            if os.path.exists(tmp_log_file):
                os.remove(tmp_log_file)
            if (parser_result <= 0):
                continue


def compute_caliper_logs(target,flag = 1):
    # according the method in the config file, compute the score
    dic = yaml.load(open(caliper_path.folder_ope.final_parser, 'r'))
    config_files = server_utils.get_cases_def_files(target)
    for i in range(0, len(config_files)):
        config_file = os.path.join(config_files[i])
        config, sections = server_utils.read_config_file(config_file)
        classify = config_files[i].split("/")[-1].strip().split("_")[0]
        for j in range(0, len(sections)):
            try:
                run_file = config.get(sections[j], 'run')
                parser = config.get(sections[j], 'parser')
            except Exception:
                raise AttributeError("The is no option value of Computing")

            print_format()
            if flag == 1:
                logging.info("Generation raw yaml for %s" % sections[j])
            else:
                logging.info("Computing Score for %s" % sections[j])
            bench = os.path.join(classify, sections[j])
            try:
                # get the abspath, which is filename of run config for the benchmark
                bench_conf_file = os.path.join(
                                caliper_path.config_files.tests_cfg_dir,
                                bench, run_file)
                # get the config sections for the benchmrk
                configRun, sections_run = server_utils.read_config_file(
                                                    bench_conf_file)
            except AttributeError as e:
                raise AttributeError
            except Exception:
                raise
            for k in range(0, len(sections_run)):
                try:
                    category = configRun.get(sections_run[k], 'category')
                    scores_way = configRun.get(sections_run[k], 'scores_way')
                    command = configRun.get(sections_run[k], 'command')
                except Exception:
                    logging.debug("no value for the %s" % sections_run[k])
                    logging.info(e)
                    continue
                scores_way1 = None

                try:
                    scores_way1 = configRun.get(sections_run[k], 'scores_way1')
                except Exception, e:
                    logging.debug(e)
                    pass

                try:
                    logging.debug("Computing the score of the result of command: %s"
                                % command)
                    if scores_way1 == None:
                        flag_compute = compute_case_score(dic[sections[j]][sections_run[k]]["value"], category,
                                          scores_way, target, flag)
                    else:
                        # if scores_way1 is defined, it menas the test case contains both types of test results:
                        # higher the better and lower the better
                        dic_name = sections_run[k] + "_latency"
                        flag_compute = compute_case_score(dic[sections[j]][sections_run[k]]["value"][dic_name], category,
                                          scores_way, target, flag)
                        dic_name = sections_run[k] + "_bandwidth"
                        flag_compute = compute_case_score(dic[sections[j]][sections_run[k]]["value"][dic_name], category,
                                          scores_way1, target, flag)
                except Exception, e:
                    logging.info("Error while computing the result of \"%s\""  % sections_run[k])
                    logging.info(e)
                    continue
                else:
                    if not flag_compute and dic[bench][sections_run[k]["value"]]:
                            logging.info("Error while computing the result\
                                        of \"%s\"" % command)
    logging.info("="*55)
    if not os.path.exists(caliper_path.HTML_DATA_DIR_INPUT):
        os.makedirs(caliper_path.HTML_DATA_DIR_INPUT)

    if not os.path.exists(caliper_path.HTML_DATA_DIR_OUTPUT):
        os.makedirs(caliper_path.HTML_DATA_DIR_OUTPUT)

def run_all_cases(target_exec_dir, target, kind_bench, bench_name,
                    run_file):
    """
    function: run one benchmark which was selected in the configuration files
    """
    try:
        # get the abspath, which is filename of run config for the benchmark
        bench_conf_file = os.path.join(
                                    caliper_path.config_files.tests_cfg_dir,
                                    kind_bench, run_file)
        # get the config sections for the benchmrk
        configRun, sections_run = server_utils.read_config_file(
                                                    bench_conf_file)
    except AttributeError as e:
        raise AttributeError
    except Exception:
        raise
    logging.debug("the sections to run are: %s" % sections_run)
    if not os.path.exists(Folder.exec_dir):
        os.mkdir(Folder.exec_dir)
    log_bench = os.path.join(Folder.exec_dir, bench_name)
    logfile = log_bench + "_output.log"
    tmp_log_file = log_bench + "_output_tmp.log"
    if os.path.exists(logfile):
        os.remove(logfile)

    starttime = datetime.datetime.now()
    if os.path.exists(Folder.caliper_log_file):
        sections = bench_name + " EXECUTION"
        fp = open(Folder.caliper_log_file,"r")
        f = fp.readlines()
        fp.close()
        op = open(Folder.caliper_log_file,"w")
        for line in f:
            if not(sections in line):
                op.write(line)
        op.close()
    result = subprocess.call("echo '$$ %s EXECUTION START: %s' >> %s"
                            % (bench_name,
                                str(starttime)[:19],
                                Folder.caliper_log_file),
                            shell=True)

    # for each command in run config file, read the config for the benchmark
    for i in range(0, len(sections_run)):
        flag = 0
        try:
            command = configRun.get(sections_run[i], 'command')
        except Exception:
            logging.debug("no value for the %s" % sections_run[i])
            continue

        if os.path.exists(tmp_log_file):
            os.remove(tmp_log_file)

        #logging.debug("Get the server command is: %s" % server_run_command)
        # run the command of the benchmarks
        try:
            flag = run_kinds_commands(sections_run[i], tmp_log_file, kind_bench, bench_name,
                                      target, command)
        except Exception, e:
            logging.info(e)
            crash_handle.main()

            server_utils.file_copy(logfile, tmp_log_file, 'a+')
            if os.path.exists(tmp_log_file):
                os.remove(tmp_log_file)

            run_flag = server_utils.get_fault_tolerance_config(
                                'fault_tolerance', 'run_error_continue')
            if run_flag == 1:
              continue
            else:
              return result
        else:
            server_utils.file_copy(logfile, tmp_log_file, 'a+')

            if flag != 1:
                logging.info("There is wrong when running the command \"%s\""
                                % command)

                if os.path.exists(tmp_log_file):
                    os.remove(tmp_log_file)
                crash_handle.main()

                run_flag = server_utils.get_fault_tolerance_config(
                                'fault_tolerance', 'run_error_continue')
                if run_flag == 1:
                    if bench_name != bench_test:
                       continue
                else:
                    return result
            if os.path.exists(tmp_log_file):
                os.remove(tmp_log_file)

    endtime = datetime.datetime.now()
    result = subprocess.call("echo '$$ %s EXECUTION STOP: %s' >> %s"
                                % (sections_run[i], str(endtime)[:19],
                                    Folder.caliper_log_file), shell=True)
    result = subprocess.call("echo '$$ %s EXECUTION DURATION %s Seconds'>>%s"
                                % (sections_run[i],
                                    (endtime-starttime).seconds,
                                    Folder.caliper_log_file), shell=True)

# normalize the commands
def get_actual_commands(commands, target):
    if commands is None or commands == '':
        return None
    post_commands = commands

    try:
        if re.findall('\$TestNode_ip_10g', commands):
            try:
                server_ip = settings.get_value('TestNode', 'TestNode_ip_10g', type=str)
            except Exception, e:
                server_ips = server_utils.get_local_ip()
                server_ip = ""

                for each_ip in server_ips:
                    items = each_ip.split(".")[0:2]
                    pre = '.'.join(items)
                    if target.ip.startswith(pre):
                        server_ip = each_ip
                        break
                if not server_ip:
                    if len(server_ips) > 1:
                        try:
                            server_ips.remove("127.0.0.1")
                        except Exception:
                            raise e

                    server_ip = server_ips[0]
            strinfo = re.compile('\$TestNode_ip_10g')
            post_commands = strinfo.sub(server_ip, commands)
    	    commands = post_commands
    except:
        pass

    try:
        if re.findall('\$target_ip_10g', commands):
            try:
                client_ip = settings.get_value('TARGET', 'target_ip_10g', type=str)
            except Exception, e:
                client_ip = '127.0.0.1'
            strinfo = re.compile('\$target_ip_10g')
            post_commands = strinfo.sub(client_ip, commands)
            commands = post_commands
    except Exception, e:
	logging.debug(e)
        pass

    try:
        if re.findall('\$target_user_name', commands):
            try:
                client_user = settings.get_value('TARGET', user, type=str)
            except:
                client_user = 'root'
            strinfo = re.compile('\$target_user_name')
            post_commands = strinfo.sub(client_user, commands)
            commands = post_commands
    except:
        pass


    actual_commands = post_commands
    if commands[0] == '\'' and commands[-1] == '\'':
        actual_commands = commands[1:-1]
    elif commands[0] == '\"' and commands[-1] == '\"':
        actual_commands = commands[1:-1]
    else:
        actual_commands = commands
    if actual_commands == '':
        return ''
    return actual_commands

def remote_commands_deal(commands, exec_dir, target):
    actual_commands = get_actual_commands(commands, target)
    final_commands = "cd %s; %s" % (exec_dir, actual_commands)
    return final_commands

def run_remote_client_commands(exec_dir, kind_bench, commands, target,
                    stdout_tee=None, stderr_tee=None):
    returncode = -1
    output = ''
    try:
        #the commands is multiple lines, and was included by Quotation
        final_commands = remote_commands_deal(commands, exec_dir, target)
        if final_commands is not None and final_commands != '':
            logging.debug("the actual commands running on the remote target"
                            "is: %s" % final_commands)
            result = target.run(final_commands, stdout_tee=stdout_tee,
                                stderr_tee=stderr_tee, verbose=True)
        else:
            return ['Not command specified', -1]
    except error.CmdError, e:
        raise error.ServRunError(e.args[0], e.args[1])
    except Exception, e:
        logging.debug(e)
    else:
        #if return status unormal or err or output is null
        if result.exit_status and result.stderr and not result.stdout:
            returncode = result.exit_status
        else:
            returncode = 0
        try:
            output = result.stdout
        except Exception:
            output = result.stderr
    return [output, returncode]

def run_client_command(cmd_sec_name, tmp_logfile, kind_bench,
                        target, command, bench_name):

    fp = open(tmp_logfile, "a+")
    #this part write log in workspace_timestamp/output/caliper_exec/hardware_info_output_tmp.log
    #if not re.search('redis', bench_name):
    start_log = "%%%%%%         %s test start       %%%%%% \n" % cmd_sec_name
    fp.write(start_log)
    fp.write("<<<BEGIN TEST>>>\n")
    tags = "[test: " + cmd_sec_name + "]\n"
    fp.write(tags)
    logs = "log: " + get_actual_commands(command, target) + "\n"
    fp.write(logs)
    start = time.time()
    flag = 0
    logging.debug("the client running command is %s" % command)

    # get the execution location in the remote host
    host_current_pwd = target.run("pwd").stdout.split("\n")[0]
    arch = server_utils.get_host_arch(target)
    host_exec_dir = os.path.join(host_current_pwd, 'caliper', "binary", arch)

    try:
        logging.debug("begining to execute the command of %s on remote host"
                        % command)
        logging.debug("client command in remote target is: %s" % command)
        [out, returncode] = run_remote_client_commands(host_exec_dir, kind_bench, command, target, fp, fp)
    except error.ServRunError, e:
        fp.write("[status]: FAIL\n")
        sys.stdout.write(e)
        flag = -1
    else:
        if not returncode:
            fp.write("[status]: PASS\n")
            flag = 1
        else:
            fp.write("[status]: FAIL\n")
            flag = 0

    end = time.time()
    interval = end - start
    fp.write("Time in Seconds: %.3fs\n" % interval)
    if not re.search('redis', bench_name):
        fp.write("<<<END>>>\n")
        fp.write("%%%%%% test_end %%%%%%\n\n")
    fp.close()
    return flag

def client_thread_func(cmd_sec_name, server_run_command, tmp_logfile,
                    kind_bench, server):
    flag = run_server_command(cmd_sec_name, server_run_command, tmp_logfile,
                    kind_bench, server, 5000)

def run_kinds_commands(cmd_sec_name, tmp_logfile, kind_bench, bench_name, target, command):
    logging.debug("only running the command %s in the remote host"%(command))
    flag = run_client_command(cmd_sec_name, tmp_logfile, kind_bench, target, command, bench_name)
    return flag

def parser_case(kind_bench, bench_name, parser_file, parser, infile, outfile):
    if not os.path.exists(infile):
        return -1
    result = 0
    fp = open(outfile, 'a+')
    # the parser function defined in the config file is to filter the output.
    # get the abspth of the parser.py which is defined in the config files.
    # changed by Elaine Aug 8-10
    if not parser_file:
        pwd_file = bench_name + "_parser.py"
        parser_file = os.path.join(caliper_path.PARSER_DIR, pwd_file)
    else:
        parser_file = os.path.join(caliper_path.PARSER_DIR, parser_file)
    rel_path = os.path.relpath(parser_file,
            os.path.dirname(caliper_path.CALIPER_DIR))
    parser_path = rel_path.split(".")[0]
    parser_name = parser_path.replace(os.sep, '.')

    result = 0
    if os.path.isfile(parser_file):
        try:
            # import the parser module import_module
            parser_module = importlib.import_module(parser_name)
        except ImportError, e:
            logging.info(e)
            return -3
        try:
            methodToCall = getattr(parser_module, parser)
        except Exception, e:
            logging.info(e)
            return -4
        else:
            infp = open(infile, "r")
            outfp = open(outfile, 'a+')
            contents = infp.read()

            for content in re.findall("BEGIN TEST(.*?)\[status\]", contents,
                                        re.DOTALL):
                try:
                    # call the parser function to filter the output
                    logging.debug("Begining to parser the result of the case")
                    result = methodToCall(content, outfp)
                except Exception, e:
                    logging.info(e)
                    return -5
            outfp.close()
            infp.close()
    fp.close()
    return result


def compute_case_score(result, category, score_way, target, flag):
    tmp = category.split()
    length = len(tmp)
    # write the result and the corresponding score to files
    target_name = server_utils.get_host_name(target)
    yaml_dir = os.path.join(Folder.results_dir, 'yaml')
    result_yaml_name = target_name + '.yaml'
    score_yaml_name = target_name + '_score.yaml'
    if flag == 1:
        result_yaml = os.path.join(yaml_dir, result_yaml_name)
    else :
        result_yaml = os.path.join(yaml_dir, score_yaml_name)
    if (length == 4 and tmp[0] == 'Functional'):
        return compute_func(result, tmp, score_way, result_yaml, flag)
    elif ((length != 0 and length <= 4) and tmp[0] == 'Performance'):
        return compute_perf(result, tmp, score_way, result_yaml, flag)
    else:
        return -4


def compute_func(result, tmp, score_way, result_yaml, flag=1):
    flag1 = 0
    if flag == 2:
        result = result * 100
    try:
        flag1 = write_results.write_yaml_func(result_yaml,
                                                tmp, result,
                                                flag)
    except BaseException:
        logging.debug("There is wrong when computing the score")
    return flag1


def compute_perf(result, tmp, score_way, result_yaml, flag=1):
    result_flag = 1
    score_flag = 2

    if type(result) is types.StringType:
        if re.search('\+', result):
            result = result.replace('\+', 'e')
        result_fp = string.atof(result)
    elif type(result) is types.FloatType:
        result_fp = result
    elif type(result) is types.IntType:
        result_fp = result
    elif (type(result) == dict and (len(tmp) > 0 and len(tmp) < 4)):
        return deal_dic_for_yaml(result, tmp, score_way,
                                    result_yaml,flag)
    else:
        return -4

    if flag == 2:
        result_fp = write_results.compute_score(score_way, result_fp)
    flag1 = 0
    try:
        flag1 = write_results.write_yaml_perf(result_yaml, tmp,
                                                result_fp, flag)
    except BaseException:
        logging.debug("There is wrong when compute the score.")
    return flag1


def deal_dic_for_yaml(result, tmp, score_way, yaml_file,flag):
    if (len(tmp) == 2):
        status = write_results.write_dic(result, tmp, score_way,
                                yaml_file, flag)
    elif (len(tmp) == 3):
        status = write_results.write_sin_dic(result, tmp, score_way, yaml_file, flag)
    else:
        status = write_results.write_multi_dic(result, tmp, score_way,
                                            yaml_file, flag)
    return status


def caliper_run(target_exec_dir, target):
    # get the test cases defined files
    config_files = server_utils.get_cases_def_files(target_exec_dir)
    logging.debug("the selected configuration are %s" % config_files)

    for i in range(0, len(config_files)):
        # run benchmarks selected in each configuration file
        # config_file = os.path.join(caliper_path.CALIPER_PRE, config_files[i])
        config_file = os.path.join(config_files[i])
        config, sections = server_utils.read_config_file(config_file)
        logging.debug(sections)

        # get if it is the 'common' or 'arm' or 'android'
        classify = config_files[i].split("/")[-1].strip().split("_")[0]
        logging.debug(classify)

        for i in range(0, len(sections)):
            # run for each benchmark
            target_arch = server_utils.get_host_arch(target)
            #server_arch = server_utils.get_host_arch(server)
            build_name = sections[i]+'_'+target_arch+'.suc'
            build_suc = os.path.join(Folder.build_dir, build_name)
            if not os.path.exists(build_suc):
	        continue
            build_host_name = sections[i] + '_' + \
            server_utils.get_local_machine_arch() + '.fail'
            if os.path.exists(build_host_name):
                continue


            # try to resolve the configuration of the configuration file
            try:
                run_file = config.get(sections[i], 'run')
                parser = config.get(sections[i], 'parser')
            except Exception:
                raise AttributeError("The is no option value of parser")

            print_format()

            logging.info("Running %s" % sections[i])
            bench = os.path.join(classify, sections[i])
            try:

                result = run_all_cases(target_exec_dir, target, bench, sections[i], run_file)

            except Exception:
                logging.info("Running %s Exception" % sections[i])
                crash_handle.main()
                print_format()

            logging.info("Running %s Finished" % sections[i])
    return 0

def parsing_run(target):
    # get the test cases defined files
    target_exec_dir = server_utils.get_target_exec_dir(target)
    config_files = server_utils.get_cases_def_files(target_exec_dir)
    logging.debug("the selected configuration are %s" % config_files)
    dic = {}
    for i in range(0, len(config_files)):
        # run benchmarks selected in each configuration file
        # config_file = os.path.join(caliper_path.CALIPER_PRE, config_files[i])
        config_file = os.path.join(config_files[i])
        config, sections = server_utils.read_config_file(config_file)
        logging.debug(sections)

        # get if it is the 'common' or 'arm' or 'android'
        classify = config_files[i].split("/")[-1].strip().split("_")[0]
        logging.debug(classify)

        for i in range(0, len(sections)):
            dic[sections[i]] = {}
            # try to resolve the configuration of the configuration file
            try:
                run_file = config.get(sections[i], 'run')
                parser = config.get(sections[i], 'parser')
            except Exception:
                raise AttributeError("The is no option value of parser")

            print_format()
            logging.info("Parsing %s" % sections[i])
            bench = os.path.join(classify, sections[i])

            try:
                result = parse_all_cases(  bench, sections[i], run_file, parser, dic)
            except Exception:
                logging.info("Parsing %s Exception" % sections[i])
                crash_handle.main()
                print_format()
                run_flag = server_utils.get_fault_tolerance_config(
                    'fault_tolerance', 'run_error_continue')
                if run_flag == 1:
                    continue
                else:
                    return result
            else:
                logging.info("Parsing %s Finished" % sections[i])
                print_format()
    outfp = open(os.path.join(caliper_path.folder_ope.workspace,
                              caliper_path.folder_ope.name.strip()
                              +"/final_parsing_logs.yaml"),'w')
    outfp.write(yaml.dump(dic, default_flow_style=False))
    outfp.close()
    return 0

def print_format():
    logging.info("="*55)


def run_caliper_tests(target, f_option):
    #f_option =1 if -f is used
    if f_option == 1:
        if not os.path.exists(Folder.exec_dir):
            os.mkdir(Folder.exec_dir)
    else:
        if os.path.exists(Folder.exec_dir):
            shutil.rmtree(Folder.exec_dir)
        os.mkdir(Folder.exec_dir)
    if not os.path.exists(Folder.results_dir):
        os.mkdir(Folder.results_dir)
    if not os.path.exists(Folder.yaml_dir):
        os.mkdir(Folder.yaml_dir)
    if not os.path.exists(Folder.html_dir):
        os.mkdir(Folder.html_dir)

    flag = 0
    target_execution_dir = server_utils.get_target_exec_dir(target)
    if not os.path.exists(target_execution_dir):
        flag = 1
    try:
        logging.debug("beginnig to run the test cases")
        test_result = caliper_run(target_execution_dir, target)

    except error.CmdError:
        logging.info("There is wrong in running benchmarks")
        flag = 1
    else:
        if test_result:
            flag = test_result
    return flag

def parser_caliper_tests(target,f_option):
    #f_option =1 if -f is used
    if not os.path.exists(Folder.exec_dir):
            print "Invalid Parser input Folder"
            return -1

    if not os.path.exists(Folder.results_dir):
        os.mkdir(Folder.results_dir)
    if not os.path.exists(Folder.yaml_dir):
        os.mkdir(Folder.yaml_dir)
    if not os.path.exists(Folder.html_dir):
        os.mkdir(Folder.html_dir)
    flag = 0
    #target_execution_dir = server_utils.get_target_exec_dir(target)
    try:
        logging.debug("beginnig to parse the test cases")
        test_result = parsing_run( target)
    except error.CmdError:
        logging.info("There is wrong in parsing test cases")
        flag = 1
    else:
        if test_result:
            flag = test_result
    return flag

if __name__ == "__main__":
    caliper_run(sys.argv[1],sys.argv[2])
