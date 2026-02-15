## Inspiration
This project was inspired by a online video series called "Hum Me a Melody", where a woman named Eunike Tanzil, a classical music composer, would ask people for a melody. Then, she would extend the melodies and turn it into. Seeing this, we wanted to streamline this process and make it into a hardware project. We wanted a playback setting for the user to get immediate feedback and an export mode to help with music production so making music won't take as long!

## What it does
Our project records the user's voice and processes the notes that the person hummed. Then, we turn these notes and extend the melody using our various python function and libraries. It is then exported into a MIDI file which is played back to the user upon interfacing with the device. To export the file, the SD card can be removed from the device!

## How we built it
**Construction: 
We used SOLIDWORKS to create a holder for all of our electrical components, which had holes for all the sensors, buttons, and user interface. 
**Electronics:
For all the processing, we used a Raspberry PI 4 to create a device that did not need internet or connection to function. We used a big sound sensor detecting the loudness levels of the user, and an audio driver to output the music. The sound sensor is connected to an Arduino that is connected to the Raspberry PI, which acts as an analog to digital converter. The user interacts with the system through buttons and a screen, which we connected to the Raspberry PI.
**Code:
We used Python on the Raspberry PI to control all of the buttons and screen, and C++ for the sound sensor and Arduino. We used numpy to do a fourier fast transform and process the sound into sine waves, finding the fundamental frequency. From there, the frequencies are matched to a note in a certain octave using Python. There is actually a general algorithm that you can use to find any note, that is by taking the note A4 which has a frequency of 440, and running 69 + 12 * $log_2(freq / A4_HZ)$, and then modulo by 12, you can get the note name.  Then we checked the major key by using a well known method called the Krumhansl-Schmuckler key-finding algorithm. By taking the importance of each note in C major and then rotating it to check for each key, we calculate by choosing the highest dot product between a histogram made from the sound data and each rotated profile. Since we are recording the melody at around 16 frames per second, we took how many consecutives notes were detecting and multiplying it by the 16 frames to find how long someone sang a note, taking into account singing the same note twice. Our songs are currently preset at 120 beats per minute with a time signature of 4/4 time, so by using pretty_midi, we extend the melody by taking the last couple of notes and raising it by two semitones, and add variety to the melody by using a I V vi IV chord structure across each bar of music.

## Challenges we ran into
Given the large nature of the Raspberry PI and its components, getting a model for the container was difficult, as the space had to be efficiently processed for quick 3D printing. 
Finding the fundamental frequency was also difficult, as often this frequency was not a part of the array of sine waves that was given. This meant if we talked into the mic, it would process a frequently that could be over 1000 hz, which is extremely high.
We also struggled to create a melody that was on time, as when we tested our MIDI files, it often placed notes ahead or behind the beat

## Accomplishments that we're proud of
meow

## What we learned
On the software side, we learned how to use various sound and musical modules/algorithms in order to correctly detect pitch. Also, as a result of making these melodies, we learned some music theory so it sounds like something someone would have head. On the hardware side, we learned how to process audio and then import the audio files made from the Python files, as well as a method to be able to convert sine waves into frequencies. 

## What's next for PiPitcher
We want to:
- implement better frequency detection
- be able to choose tempo to suit the type of music you want to make
- select your genre and set up preset instrumentation if you already made a beat
- improve our UI
- create more advanced melody extension algorithms
