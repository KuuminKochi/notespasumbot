import pty
import os
import time
import select

password = "-af29426101"
cmd = "ssh-copy-id -i ~/.ssh/notespasumbot_deploy.pub -o StrictHostKeyChecking=no root@152.42.245.71"

print(f"Running: {cmd}")
pid, fd = pty.fork()

if pid == 0:
    os.execv("/bin/sh", ["sh", "-c", cmd])
else:
    output = b""
    while True:
        r, _, _ = select.select([fd], [], [], 2)
        if not r:
            break
        try:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            output += chunk
            print(f"Read: {chunk.decode()}")

            if b"password:" in output.lower():
                print(">>> Sending password...")
                os.write(fd, (password + "\n").encode())
                # Clear buffer to avoid re-sending
                output = b""
                # Wait for result
                time.sleep(1)
        except OSError:
            break

    print("Done.")
