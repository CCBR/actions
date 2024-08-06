import subprocess


def shell_run(cmd_str):
    run = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    return "\n".join([run.stdout, run.stderr])
