# Release reply queue

Replies to post after the next release, on threads that no released commit references with `#N`. Those get replies automatically. The "govee daily release" routine posts each entry below after it creates the release, then empties this list and commits that. On a night with no release, the entries wait.

Add one `##` section per thread:
- `close: yes|no`: close the thread after replying. Only use `yes` when the reporter confirmed the fix or asked for it to be closed.
- `brief:` what the reply must say. The routine writes the comment from the brief, citing the released version only where the brief asks for it.

<!-- entries below; the routine removes them once posted -->
