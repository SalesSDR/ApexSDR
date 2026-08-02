import asyncio
import httpx
import time
import argparse
import statistics

async def fetch(client, url, method="GET", payload=None):
    start_time = time.perf_counter()
    try:
        if method == "GET":
            response = await client.get(url)
        else:
            response = await client.post(url, json=payload)
        latency = time.perf_counter() - start_time
        return response.status_code, latency
    except Exception as e:
        return 0, time.perf_counter() - start_time

async def load_test(url, num_requests, concurrency, method="GET", payload=None):
    print(f"Starting load test on {url} with {num_requests} requests (concurrency: {concurrency})")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        sem = asyncio.Semaphore(concurrency)
        
        async def bound_fetch():
            async with sem:
                return await fetch(client, url, method, payload)
        
        start_time = time.perf_counter()
        
        # Batch tasks
        tasks = [bound_fetch() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.perf_counter() - start_time
        
        status_codes = {}
        latencies = []
        
        for status, latency in results:
            status_codes[status] = status_codes.get(status, 0) + 1
            latencies.append(latency)
            
        print("\n--- Load Test Results ---")
        print(f"Total Requests: {num_requests}")
        print(f"Concurrency Level: {concurrency}")
        print(f"Time taken for tests: {total_time:.2f} seconds")
        print(f"Requests per second: {num_requests / total_time:.2f} req/s")
        
        print("\nStatus Codes:")
        for code, count in sorted(status_codes.items()):
            print(f"  {code}: {count}")
            
        if latencies:
            print("\nLatency Distribution:")
            print(f"  Min: {min(latencies):.4f}s")
            print(f"  Max: {max(latencies):.4f}s")
            print(f"  Mean: {statistics.mean(latencies):.4f}s")
            print(f"  Median: {statistics.median(latencies):.4f}s")
            if len(latencies) >= 2:
                print(f"  Stdev: {statistics.stdev(latencies):.4f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lightweight Load Tester for ApexSDR")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/v1/health/readiness")
    parser.add_argument("--requests", "-n", type=int, default=100)
    parser.add_argument("--concurrency", "-c", type=int, default=10)
    parser.add_argument("--method", "-m", type=str, default="GET")
    
    args = parser.parse_args()
    asyncio.run(load_test(args.url, args.requests, args.concurrency, args.method))
