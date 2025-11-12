"""
Test script to verify S3 access and PDF retrieval.

This script tests:
- AWS credentials are valid
- S3 bucket is accessible
- Can list objects in bucket
- Can fetch PDF files
- Can read PDF metadata
"""
import sys
import os
# Add parent directory to path so we can import from services/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config.settings import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


def get_s3_client():
    """Get S3 client with proper credentials."""
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        logger.info("Using explicit AWS credentials")
        return boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
    else:
        logger.info("Using default AWS credential chain")
        return boto3.client('s3', region_name=settings.aws_region)


async def test_s3_connectivity():
    """Quick test to verify S3 access and credentials."""
    
    print("=" * 80)
    print("S3 CONNECTIVITY TEST")
    print("=" * 80)
    
    print("\n📋 Configuration:")
    print(f"   Region: {settings.aws_region}")
    print(f"   Access Key: {'*' * 10}{settings.aws_access_key_id[-4:] if settings.aws_access_key_id else 'NOT SET (using default)'}")
    print(f"   Default Bucket: {settings.s3_output_bucket or 'NOT SET'}")
    
    try:
        print("\n🚀 Step 1: Creating S3 client...")
        s3_client = get_s3_client()
        print("✅ S3 client created")
        
        print("\n🚀 Step 2: Testing credentials with list_buckets...")
        response = await asyncio.to_thread(s3_client.list_buckets)
        
        buckets = response.get('Buckets', [])
        print(f"✅ SUCCESS! Found {len(buckets)} accessible buckets")
        
        if buckets:
            print("\n📦 Accessible Buckets:")
            for bucket in buckets[:10]:  # Show first 10
                print(f"   - {bucket['Name']}")
            if len(buckets) > 10:
                print(f"   ... and {len(buckets) - 10} more")
        
        return True
        
    except NoCredentialsError:
        print("\n❌ FAILED: No AWS credentials found")
        print("   Please configure AWS credentials:")
        print("   - Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to .env")
        print("   - Or run 'aws configure' to set up AWS CLI credentials")
        return False
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"\n❌ FAILED: AWS Error - {error_code}")
        print(f"   Message: {e.response['Error']['Message']}")
        return False
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        logger.error(f"Connectivity test failed: {e}", exc_info=True)
        return False


async def test_list_bucket_objects(bucket_name: str, prefix: str = "", max_keys: int = 20):
    """List objects in a specific bucket."""
    
    print("=" * 80)
    print("LIST BUCKET OBJECTS TEST")
    print("=" * 80)
    
    print(f"\n📋 Parameters:")
    print(f"   Bucket: {bucket_name}")
    print(f"   Prefix: {prefix or '(root)'}")
    print(f"   Max Keys: {max_keys}")
    
    try:
        s3_client = get_s3_client()
        
        print(f"\n🚀 Listing objects in '{bucket_name}'...")
        
        params = {
            'Bucket': bucket_name,
            'MaxKeys': max_keys
        }
        if prefix:
            params['Prefix'] = prefix
        
        response = await asyncio.to_thread(s3_client.list_objects_v2, **params)
        
        if 'Contents' not in response:
            print(f"\n⚠️  No objects found in bucket '{bucket_name}'")
            if prefix:
                print(f"   Try without prefix or check if prefix '{prefix}' exists")
            return []
        
        objects = response['Contents']
        print(f"\n✅ Found {len(objects)} objects")
        
        if response.get('IsTruncated'):
            print(f"   ⚠️  Results truncated (more objects available)")
        
        # Separate PDFs from other files
        pdfs = [obj for obj in objects if obj['Key'].lower().endswith('.pdf')]
        other = [obj for obj in objects if not obj['Key'].lower().endswith('.pdf')]
        
        if pdfs:
            print(f"\n📄 PDF Files ({len(pdfs)}):")
            for obj in pdfs[:10]:
                size_mb = obj['Size'] / (1024 * 1024)
                modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"   • {obj['Key']}")
                print(f"     Size: {size_mb:.2f} MB | Modified: {modified}")
            if len(pdfs) > 10:
                print(f"   ... and {len(pdfs) - 10} more PDFs")
        
        if other:
            print(f"\n📁 Other Files ({len(other)}):")
            for obj in other[:5]:
                size_kb = obj['Size'] / 1024
                print(f"   • {obj['Key']} ({size_kb:.1f} KB)")
            if len(other) > 5:
                print(f"   ... and {len(other) - 5} more files")
        
        return pdfs
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"\n❌ FAILED: {error_code}")
        if error_code == 'NoSuchBucket':
            print(f"   Bucket '{bucket_name}' does not exist")
        elif error_code == 'AccessDenied':
            print(f"   Access denied to bucket '{bucket_name}'")
            print(f"   Check your IAM permissions")
        else:
            print(f"   Message: {e.response['Error']['Message']}")
        return []
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        logger.error(f"List objects failed: {e}", exc_info=True)
        return []


async def test_fetch_pdf(bucket_name: str, key: str):
    """Test fetching a specific PDF from S3."""
    
    print("=" * 80)
    print("FETCH PDF TEST")
    print("=" * 80)
    
    print(f"\n📋 Target:")
    print(f"   Bucket: {bucket_name}")
    print(f"   Key: {key}")
    print(f"   S3 URI: s3://{bucket_name}/{key}")
    
    try:
        s3_client = get_s3_client()
        
        print(f"\n🚀 Step 1: Getting object metadata...")
        head_response = await asyncio.to_thread(
            s3_client.head_object,
            Bucket=bucket_name,
            Key=key
        )
        
        size_mb = head_response['ContentLength'] / (1024 * 1024)
        content_type = head_response.get('ContentType', 'unknown')
        last_modified = head_response['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"✅ Object exists")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Content Type: {content_type}")
        print(f"   Last Modified: {last_modified}")
        
        print(f"\n🚀 Step 2: Downloading object...")
        start_time = datetime.utcnow()
        
        response = await asyncio.to_thread(
            s3_client.get_object,
            Bucket=bucket_name,
            Key=key
        )
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # Read first chunk to verify it's readable
        body = response['Body']
        first_chunk = body.read(1024)  # Read first 1KB
        body.close()
        
        print(f"✅ Download successful! (took {elapsed:.2f}s)")
        print(f"   First chunk size: {len(first_chunk)} bytes")
        
        # Check if it's a valid PDF
        if first_chunk.startswith(b'%PDF'):
            print(f"   ✅ Valid PDF header detected")
        else:
            print(f"   ⚠️  Warning: File doesn't start with PDF header")
            print(f"   First bytes: {first_chunk[:20]}")
        
        print("\n" + "=" * 80)
        print("✅ TEST PASSED: PDF is accessible")
        print("=" * 80)
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"\n❌ FAILED: {error_code}")
        if error_code == 'NoSuchKey':
            print(f"   Object '{key}' not found in bucket '{bucket_name}'")
            print(f"   Check the key path is correct")
        elif error_code == 'AccessDenied':
            print(f"   Access denied to object")
        else:
            print(f"   Message: {e.response['Error']['Message']}")
        return False
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        logger.error(f"Fetch PDF failed: {e}", exc_info=True)
        return False


async def test_s3_full():
    """Complete S3 test workflow."""
    
    print("=" * 80)
    print("S3 FULL ACCESS TEST")
    print("=" * 80)
    
    # Test 1: Connectivity
    print("\n" + "─" * 80)
    print("Test 1: Connectivity")
    print("─" * 80)
    success = await test_s3_connectivity()
    if not success:
        return False
    
    await asyncio.sleep(1)
    
    # Test 2: List bucket objects
    print("\n" + "─" * 80)
    print("Test 2: List Objects")
    print("─" * 80)
    
    # Use rm-conditions bucket (commonly used in examples)
    bucket = "rm-conditions"
    print(f"\nTrying default bucket: {bucket}")
    pdfs = await test_list_bucket_objects(bucket, max_keys=10)
    
    if not pdfs:
        print("\n⚠️  No PDFs found. Let's try the configured bucket...")
        if settings.s3_output_bucket:
            bucket = settings.s3_output_bucket.split('/')[0]  # Extract bucket name
            pdfs = await test_list_bucket_objects(bucket, max_keys=10)
    
    await asyncio.sleep(1)
    
    # Test 3: Fetch a PDF
    if pdfs:
        print("\n" + "─" * 80)
        print("Test 3: Fetch PDF")
        print("─" * 80)
        
        # Try to fetch the first PDF found
        pdf = pdfs[0]
        await test_fetch_pdf(bucket, pdf['Key'])
    else:
        print("\n⚠️  Skipping PDF fetch test (no PDFs found)")
    
    print("\n" + "=" * 80)
    print("✅ FULL S3 TEST COMPLETED")
    print("=" * 80)


async def test_specific_pdf():
    """Test a specific PDF that's used in your workflow."""
    
    print("=" * 80)
    print("TEST SPECIFIC PDF")
    print("=" * 80)
    
    # Common test PDFs from your workflow
    test_cases = [
        {
            "name": "Preliminary Title Report",
            "bucket": "rm-conditions",
            "key": "Encompass Docs - Preliminary Title Report dtd 9-4-25.pdf"
        },
        {
            "name": "Flood Certificate",
            "bucket": "rm-conditions",
            "key": "Flood Certification - Flood Certificate.pdf"
        },
        {
            "name": "Wiring Instructions",
            "bucket": "quick-quote-demo",
            "key": "mock/Wiring Instructions - demo.pdf"
        }
    ]
    
    print("\nTesting common PDFs from workflow...")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'─' * 80}")
        print(f"Test Case {i}: {test_case['name']}")
        print(f"{'─' * 80}")
        
        success = await test_fetch_pdf(test_case['bucket'], test_case['key'])
        
        if success:
            print(f"✅ {test_case['name']} is accessible")
        else:
            print(f"❌ {test_case['name']} is NOT accessible")
        
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("S3 Access Test Script")
    print("=" * 80)
    print("\nOptions:")
    print("  1. Quick connectivity test (check AWS credentials)")
    print("  2. List objects in bucket (browse S3)")
    print("  3. Test specific PDF access")
    print("  4. Full test (all of the above)")
    print()
    
    choice = input("Select test [1/2/3/4] (default: 1): ").strip() or "1"
    
    if choice == "1":
        print("\n🔬 Running QUICK connectivity test...")
        success = asyncio.run(test_s3_connectivity())
        sys.exit(0 if success else 1)
        
    elif choice == "2":
        bucket = input("\nEnter bucket name (default: rm-conditions): ").strip() or "rm-conditions"
        prefix = input("Enter prefix/folder (optional, press Enter to skip): ").strip()
        print(f"\n🔬 Listing objects in '{bucket}'...")
        asyncio.run(test_list_bucket_objects(bucket, prefix=prefix, max_keys=50))
        
    elif choice == "3":
        print("\n🔬 Testing specific PDFs from workflow...")
        asyncio.run(test_specific_pdf())
        
    elif choice == "4":
        print("\n🔬 Running FULL test suite...")
        asyncio.run(test_s3_full())
        
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

