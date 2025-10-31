"""FastAPI application - Main entry point"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.schemas import ExecuteRequest, ExecuteResponse, HealthResponse
from app.core.service import service
from app.core.exceptions import ValidationError, ExecutionError
from app.config import get_settings
from app.storage.manager import init_storage_manager
from app.executors.factory import get_healthy_executor, ExecutorFactory

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Secure Python code execution sandbox for AI agents",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - allow all origins for AI agent access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log request info
    print(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {duration:.3f}s"
    )

    return response


# Exception handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors with proper HTTP status"""
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "Validation failed",
            "message": str(exc),
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
            "execution_time": 0.0,
            "files": []
        }
    )


@app.exception_handler(ExecutionError)
async def execution_error_handler(request: Request, exc: ExecutionError):
    """Handle execution errors with proper HTTP status"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Execution failed",
            "message": str(exc),
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
            "execution_time": 0.0,
            "files": []
        }
    )


# API Routes
@app.post("/execute", response_model=ExecuteResponse, tags=["Execution"])
async def execute_code(request: ExecuteRequest):
    """
    Execute Python code in a secure sandbox

    This endpoint allows AI agents to execute Python code safely with:
    - Syntax and security validation
    - Resource limits (CPU, memory, timeout)
    - Network isolation
    - Read-only filesystem

    **Example Request:**
    ```json
    {
        "code": "print('Hello, World!')",
        "timeout": 10
    }
    ```

    **Example Response:**
    ```json
    {
        "success": true,
        "stdout": "Hello, World!\\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time": 0.234,
        "error": null,
        "files": []
    }
    ```
    """
    try:
        result = await service.execute_code(
            code=request.code,
            timeout=request.timeout
        )
        return ExecuteResponse(**result)

    except ValidationError as e:
        # ValidationError is handled by exception handler
        raise

    except ExecutionError as e:
        # ExecutionError is handled by exception handler
        raise

    except Exception as e:
        # Unexpected error
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns the health status of the service and its dependencies.
    Use this to monitor service availability.

    **Example Response:**
    ```json
    {
        "status": "healthy",
        "version": "1.0.0",
        "executor": {
            "provider": "docker",
            "healthy": true,
            "available_providers": ["docker"],
            "active_providers": ["docker"]
        }
    }
    ```
    """
    # Check executor health
    executor_healthy = False
    executor_name = "unknown"

    try:
        executor = await get_healthy_executor()
        executor_healthy = True
        executor_name = executor.get_name()
    except Exception as e:
        print(f"Health check: Executor unavailable - {e}")

    # Get storage health
    from app.storage import get_storage_manager
    storage_manager = get_storage_manager()
    storage_healthy = await storage_manager.health_check() if storage_manager else True

    return {
        "status": "healthy" if executor_healthy else "degraded",
        "version": settings.VERSION,
        "executor": {
            "provider": settings.EXECUTOR_PROVIDER,
            "name": executor_name,
            "healthy": executor_healthy,
            "fallbacks": settings.EXECUTOR_FALLBACK_PROVIDERS,
            "available_providers": ExecutorFactory.get_available_providers(),
            "active_providers": ExecutorFactory.get_active_providers()
        },
        "storage": {
            "enabled": storage_manager.is_enabled() if storage_manager else False,
            "healthy": storage_healthy
        }
    }


@app.get("/", tags=["Info"])
async def root():
    """
    Root endpoint with service information

    Returns basic information about the service and available endpoints.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "endpoints": {
            "execute": "POST /execute",
            "health": "GET /health",
            "docs": "GET /docs",
            "redoc": "GET /redoc"
        },
        "description": "Secure Python code execution sandbox for AI agents"
    }


# Startup event
@app.on_event("startup")
async def startup():
    """Run startup checks"""
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} starting...")

    # Initialize storage if enabled
    if settings.STORAGE_ENABLED:
        try:
            storage_config = {
                'bucket_name': settings.STORAGE_R2_BUCKET,
                'account_id': settings.STORAGE_R2_ACCOUNT_ID,
                'access_key_id': settings.STORAGE_R2_ACCESS_KEY,
                'secret_access_key': settings.STORAGE_R2_SECRET_KEY,
                'prefix': settings.STORAGE_R2_PREFIX,
                'public_url': settings.STORAGE_R2_PUBLIC_URL or None
            }
            storage_manager = init_storage_manager(
                provider_type=settings.STORAGE_PROVIDER,
                config=storage_config
            )
            
            # Test storage health
            if await storage_manager.health_check():
                print(f"✅ Storage ready (provider: {settings.STORAGE_PROVIDER})")
            else:
                print(f"⚠️  WARNING: Storage provider {settings.STORAGE_PROVIDER} is not healthy!")
        except Exception as e:
            print(f"⚠️  WARNING: Failed to initialize storage: {e}")
            print("    Service will continue without file storage")
    else:
        # Initialize disabled storage
        init_storage_manager(provider_type='disabled')
        print("ℹ️  Storage is disabled")

    # Verify executor health
    try:
        executor = await get_healthy_executor()
        print(f"✅ Executor ready: {executor.get_name()} (provider: {settings.EXECUTOR_PROVIDER})")

        # Show fallback providers if configured
        fallback_providers = settings.EXECUTOR_FALLBACK_PROVIDERS
        if fallback_providers and fallback_providers != settings.EXECUTOR_PROVIDER:
            print(f"   Fallback providers: {fallback_providers}")

        # Show available providers
        available_providers = ExecutorFactory.get_available_providers()
        print(f"   Available providers: {', '.join(available_providers)}")

    except Exception as e:
        print(f"⚠️  WARNING: No healthy executor available: {e}")
        print(f"    Primary provider: {settings.EXECUTOR_PROVIDER}")
        print(f"    Fallback providers: {settings.EXECUTOR_FALLBACK_PROVIDERS}")
        print("    Service will start but /execute endpoint will fail until an executor is available")

    print(f"📡 API available at http://{settings.HOST}:{settings.PORT}")
    print(f"📚 Documentation at http://{settings.HOST}:{settings.PORT}/docs")


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    """Run cleanup on shutdown"""
    print(f"🛑 {settings.APP_NAME} shutting down...")

    # Cleanup all executors
    ExecutorFactory.cleanup_all()

    print("✅ Cleanup complete")


# Run with: uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
