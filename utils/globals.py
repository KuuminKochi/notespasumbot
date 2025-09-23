question_map = {}  # {admin_msg_id: (q_text, asker, asker_id, media)}
active_users = set()  # { (user_id, username/full_name) }

INTRODUCTION = """
Hello, my name is Mimi. I'm your dedicated Notes PASUM 25/26 Bot!

I apologize as I'm a little barebones right now, because my stupid creator, Anthonny, decided to code this in the middle of the night! However, I will still try my best to support you the best I can!

To use me, please directly message me, and ensure that your questions exceed at least 10 characters with a \"?\" at the very end of your question. Here's an example:

Help - BAD!
How do I solve this question - BAD!
I'm getting really confused because of x and y, could you tell me how to solve it? - GOOD!

If you have any attachments, DO NOT SEND IT SEPARATELY WITH YOUR MESSAGE!

My creator made me so that Faith wouldn't be so overwhelmed in responding to billions of DMs asking for help. Now, please use me as an intermediary for you to ask question! This time, both Anthonny and Faith can actually answer your questions rather than only one person at once.
"""

HELP = """
Hi! This is how you use me:
1. Privately DM me any questions you have as long as it is more than 5 letters long!
2. If you need to send any images alongside your question, please add captions alongside your message so that your message can go through the admins.

That's all! Simple right? 😁
These are some alternative commands I can do:
/pasummatch - This was made due to the incessant request of Arman Roommate Anthonny
"""

TUTORIAL_ANSWERS = """
Faith Law's Tutorial Answers (For reference):

Chemistry ;
T1-2 General Chem ; https://drive.google.com/file/d/1PxIzVqDXbje2HPg5fnvRnwmSPKKgdeni/view?usp=drivesdk
T3 States of Matter ; https://drive.google.com/file/d/1-TzgLXINKo-ysUq5sBnhthHEuT3f2hfK/view?usp=drivesdk
T4 Atomic Structure ; https://drive.google.com/file/d/1rPR78qDGTWhJJdzRSIHdPcNjaEpJgtMu/view?usp=drivesdk
T5 PTE pt.1 ; https://drive.google.com/file/d/167mALpmofdttN73HLHqEBRpdYXqnhHL9/view?usp=drivesdk
T6 PTE pt.2 ; https://drive.google.com/file/d/1teuIWFm-XbnxeMrJTZlixXqWqU3ixLak/view?usp=drivesdk

Physics ;
https://drive.google.com/drive/folders/1OcQLAAquqXZADKEa-sNlAmaoch7sNTiQ

Maths ;
https://drive.google.com/drive/folders/181DJTteyZg6oIUcH7_E9dSjm4ZdaM6sW

Advanced Mathematics ;
https://drive.google.com/drive/folders/1mhu8HySUjz60Tj28fnp-FFGdyd0dsoG2

Programming ;
https://drive.google.com/drive/folders/1r4_Q-iMid-j5Ge9KXIAOTMLfBbSOcg_X

Let's all say "Thanks, Faith!"
"""

LECTURE_NOTES = """
SPeCTRUM - https://spectrum.um.edu.my/my/courses.php
Lecture Notes and Tutorials - https://drive.google.com/drive/u/0/folders/1CUHpAQTSco5Mw4trLUR6setVAX9E7wNl

Message @AnthonNYN if anything is missing!
"""
