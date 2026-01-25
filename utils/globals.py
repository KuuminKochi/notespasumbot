question_map = {}  # {admin_msg_id: (q_text, asker, asker_id, media)}
active_users = set()  # { (user_id, username/full_name) }

WARNING = """
"""

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

<b>📰 News & Submissions:</b>
/news - View latest PASUM news and updates with pagination
/post - Submit a post with optional image/PDF for Mimi to moderate and categorize
/post reply [ID] [text] - Reply to a specific news post by its ID

<b>🤝 Community:</b>
/pasummatch - Find and connect with other PASUM students

<b>📚 Academic Resources:</b>
/tutorials - Access tutorial answers
/lecturenotes - Get lecture notes and resources
/jottednotes - Access jotted study notes

<b>👤 Profile:</b>
/profile - View or update your profile
/random - Discover a random PASUM student's profile

<b>⚙️ Bot Management:</b>
/reset - Clear your conversation context (soft reset)
/hardreset - Complete reset of all your data
"""

TUTORIAL_ANSWERS = """
Anthonny's Tutorial Answers (Tutorial 10 and Onwards - WARNING: UPLOADED AS SOON AS POSSIBLE, UPDATED AFTER TUTORIAL DISCUSSION!):
https://drive.google.com/drive/folders/19uqPopybpk72RhcGBKkJF_ANGmFn6EBw
"""

OLD_TUTORIAL_ANSWERS = """
Faith Law's Tutorial Answers (For reference):

Mathematics:
https://drive.google.com/drive/folders/1cXHcBxx-c6gw6MaeNjsUOoDB02lpmbEe

Advanced Mathematics:
https://drive.google.com/drive/folders/1AxKhn_FQ0NQ0MKjSjRhHLYsyHY7Md85b

Chemistry:
https://drive.google.com/drive/folders/1QwxeAQBRaiTA6lU7OMnK-ZrkXkSkC7q5

Physics:
https://drive.google.com/drive/folders/1FJGivZOmhWhb1Bzov1zdoWl2U3NwBuUW

Let's all say "Thanks, Faith!"

Anthonny's Tutorial Answers (Tutorial 10 and Onwards - WARNING: UPLOADED AS SOON AS POSSIBLE, UPDATED AFTER TUTORIAL DISCUSSION!):
https://drive.google.com/drive/folders/19uqPopybpk72RhcGBKkJF_ANGmFn6EBw
"""

JOTTED_NOTES = """
Anthonny's Jotted Notes:
https://drive.google.com/drive/folders/1eFzchsHLkviLTfIOjuoRMVoCnx2wkZK0
"""

LECTURE_NOTES = """
SPeCTRUM - https://spectrum.um.edu.my/my/courses.php
Physical Lecture Notes and Tutorials - https://drive.google.com/drive/u/0/folders/1CUHpAQTSco5Mw4trLUR6setVAX9E7wNl
Social Science Lecture Notes and Tutorials - https://drive.google.com/drive/u/1/folders/1-KUyNtiMlLY38eKQJGp67racKvRNNAFx
*Check MUET*
https://mecea.mpm.edu.my/MUETD/index.php

Message @AnthonNYN if anything is missing!
"""


MID_SEM = """

*UPS Sem 1*

*FAD1013 Mathematics I*
Tutorial 1 - Tutorial 6

*FAD1016 Basic Chemistry I*
Tutorial 1 - Tutorial 6

*FAD1020 Basic Physic I*
Tutorial 1 - Tutorial 8

*FAC1001 Advance Mathematics I*
Tutorial 1 - Tutorial 6

*FAC1002 Programming I*
Malware - L04
Control Unit (CU) in the CPU - L02
Primary Memory - L03
Truth Table L07
Boolean Algebra Expression - L09
Logic Circuit (Figure/Diagram) - L10
Simplify Logic Expression - L10
8/13/16-Bit Memory
32-Bit (Single-Precision)
Basic Logic Gates (NOT, AND, and OR Gates) - L09
Integer Variables = L11, L12, L13, L14, L15, L16
C++ Code - sqrt(), pow(), frac()
"""
