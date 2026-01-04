import pty
import os
import time

password = "-af29426101"
cmd = "ssh-copy-id -i ~/.ssh/notespasumbot_deploy.pub -o StrictHostKeyChecking=no root@152.42.245.71"

print(f"Running: {cmd}")
pid, fd = pty.fork()

if pid == 0:
    # Child process
    os.execv("/bin/sh", ["sh", "-c", cmd])
else:
    # Parent process
    time.sleep(1)
    output = os.read(fd, 1024).decode()
    print(f"Output: {output}")

    if "password:" in output.lower():
        print("Sending password...")
        os.write(fd, (password + "\n").encode())
        time.sleep(2)
        final_output = os.read(fd, 1024).decode()
        print(f"Final Output: {final_output}")
    else:
        print("Did not receive password prompt as expected.")
