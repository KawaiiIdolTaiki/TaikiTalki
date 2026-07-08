# TaikiTalki
stolen project from https://github.com/SweepTosher/dumper

---

ok i am finally done this time. i have updated the events.json to include all and every events in the game(i hope so)
next update would be on grand live/grand concert whatever and i probably take some time to update new umas until someone
pestered me enough to do so or i get motivation to do them 

---

Taikitalki
Event Outcome Resolver for the hit game Umamusume: Pretty Derby

if you are using this just be prepared if you suddenly get a love letter from saige

i made this thing more braindead easy to use now so uhh
ok i have tested everything and yea everything should work. even the events.json is done
i think from now till the day this thing dies ill do minimal adjustments to events.json or minor patches to other stuffs(<- lies look at what happen on 1.5 patch)

oh welp gl and have fun with this thing

---

basically what this is, it just gives you the best outcome for every gambling event
i stole the dumper from sweepy but i populate the events.json to include all events in the game
if you wanted to steal my events.json and make your own project, i am fine with it, but i would love to hear what you
are going to do with it so just contact me or something

and if you wanted to know how majority of the event works

Literally every single events -> odd = good
exception
meek challenge(ura) -> value: 1,2 = good
infirmary -> value 2 = good, or even = good
unsure? -> etsuko exhaustive coverage -> ????

MANT specific
all post-race event -> value: 1,2 = good
infirmary -> even = good

i think thats it for the summarization? 
everything else is in the events.json for further detail 

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/KawaiiIdolTaiki/TaikiTalki 
cd taikitalki-main
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Let Taiki whisper into your ear

open launch.bat

or

```bash
python taikitalki.py
```
```bash
python dumper.py
```

dont close the terminals(this goes without saying)

---

## Firefox stuffs
program is tested only on firefox and idc about other browser

### Enable popup on firefox

### Change the size and positions directly in the program

## Troubleshooting

### Dumper wont run
1. Start the game first(lmao)

2. run dumper.py as administrator

3. Restart computer(tried and tested method)

### If the event refreshes very slowly(not instant)
-delete dump folder
-restart the program

## Changelog
### 09-07-2026
    -updated all support cards and uma events up to baeboo memory(i love her)
    also all events including scenario, and other miscellanous events are done

### 03-07-2026
    -bandaid patch so it works with all other scenario(please update other event i am crine)

### 02-07-2026
    -placeholder meek event(havent updated the other event yet)

### 14-06-2026
    -sweep fatty event updated(gambling broke)

### 10-06-2026
    -full global event updated

### 09-06-2026
    -dumper update if it doesnt want to open(i shot the port and freed it for the process)

### 08-06-2026
    -updated events.json to include all events(uma,support,scenario)
    -fixed always on top(again, but should works fine now)
    -auto dump made(yey)
    -make it more braindead easy to use
### 08-05-2026
    -fix always on top
    -more maps
