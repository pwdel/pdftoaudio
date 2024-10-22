## To Run:

* Place a text PDF within the books/ directory.
* Within the project root directory, run `./read pdf ${pdf_name.pdf}` in the terminal.
* App will give a rough estimate on the cost to convert to audio .mp3 file using Google TTS standard.


## About Google TTS Quotas

* As of writing this readme file, Google TTS imposes a 5000 bytes per request quota, and a 1000 requests per minute quota.
* Therefore:

```
(5000 bytes/request)(1000 requests/minute) = 5000000 bytes/minute = 5M bytes/minute
```

* If appropriately chunked, assuming there are 300,000 characters in a large document, this would suggest around 16 large documents per minute can be processed.
* That being said, the free tier of Google TTS is 1,000,000 or 1M bytes, so after 1M bytes there would be a cost per byte.
* Bytes are approximately equal to one character, accepting special characters which may be more than one byte, but our cost estimation function assumes incorrectly that 1 character = 1 byte.


[Google TTS Quotas](https://cloud.google.com/text-to-speech/quotas)