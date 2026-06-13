import aasu


mgr = aasu.WorkerManager("movie-workers")
mgr.connect("redis://localhost:6379/1")


@mgr.worker()
async def log_movie(title: str):
    print(f"Logging movie: {title}")


mgr.start()
