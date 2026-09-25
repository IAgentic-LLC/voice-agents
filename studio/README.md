# Voice Agent Studio

Chapter 32's React frontend for Chapter 31's agent registry: version
history, an editor for writing new versions, and a playground that
places a real live call against whichever version is current.

```
npm install
npm run dev
```

Needs, running separately (see the chapter for exact commands): the
FastAPI backend (`studio_api.py`, in the parent directory) and a
`dynamic_agent.py` worker for whichever agent you select.

```
npm test        # vitest, the store's own logic
npx tsc --noEmit # type check
```
