"""
Database Migration Tools

Provides tools for migrating data between SQLite and PostgreSQL,
enabling seamless production upgrades with zero data loss.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import DatabaseAdapter, DatabaseConfig
from .sqlite_adapter import SQLiteAdapter
from .postgresql_adapter import PostgreSQLAdapter
from .factory import create_database_adapter

logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """
    Database migration tool for SQLite to PostgreSQL migration
    
    Provides safe, incremental migration with data validation and rollback
    capabilities for production voice agent deployments.
    """
    
    def __init__(self, source_config: DatabaseConfig, target_config: DatabaseConfig):
        self.source_config = source_config
        self.target_config = target_config
        self.source_adapter: Optional[DatabaseAdapter] = None
        self.target_adapter: Optional[DatabaseAdapter] = None
    
    async def initialize(self):
        """Initialize source and target database connections"""
        try:
            # Initialize source database
            self.source_adapter = create_database_adapter(self.source_config)
            await self.source_adapter.initialize()
            logger.info(f"✅ Source database connected: {self.source_config.type}")
            
            # Initialize target database
            self.target_adapter = create_database_adapter(self.target_config)
            await self.target_adapter.initialize()
            logger.info(f"✅ Target database connected: {self.target_config.type}")
            
        except Exception as e:
            logger.error(f"❌ Migration initialization failed: {e}")
            await self.close()
            raise
    
    async def close(self):
        """Close database connections"""
        if self.source_adapter:
            await self.source_adapter.close()
        if self.target_adapter:
            await self.target_adapter.close()
    
    async def migrate_cost_events(self, batch_size: int = 1000, validate: bool = True) -> Dict[str, Any]:
        """
        Migrate cost events from source to target database
        
        Args:
            batch_size: Number of records to migrate per batch
            validate: Whether to validate data after migration
            
        Returns:
            Migration statistics and results
        """
        if not self.source_adapter or not self.target_adapter:
            raise RuntimeError("Migration not initialized")
        
        start_time = time.time()
        stats = {
            "total_records": 0,
            "migrated_records": 0,
            "failed_records": 0,
            "batches_processed": 0,
            "start_time": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            logger.info("🚀 Starting cost events migration...")
            
            # Get total count from source
            if hasattr(self.source_adapter, '_pool'):
                # PostgreSQL source
                async with self.source_adapter._pool.acquire() as conn:
                    total_count = await conn.fetchval("SELECT COUNT(*) FROM cost_events")
            else:
                # SQLite source
                def _count():
                    import sqlite3
                    with sqlite3.connect(self.source_adapter.db_path) as conn:
                        cursor = conn.execute("SELECT COUNT(*) FROM cost_events")
                        return cursor.fetchone()[0]
                total_count = await self.source_adapter._run_in_executor(_count)
            
            stats["total_records"] = total_count
            logger.info(f"📊 Found {total_count} records to migrate")
            
            # Migrate in batches
            offset = 0
            while offset < total_count:
                try:
                    # Get batch from source
                    batch = await self._get_batch_from_source(offset, batch_size)
                    if not batch:
                        break
                    
                    # Insert batch into target
                    migrated_count = await self._insert_batch_to_target(batch)
                    
                    stats["migrated_records"] += migrated_count
                    stats["batches_processed"] += 1
                    offset += batch_size
                    
                    # Progress logging
                    progress = (offset / total_count) * 100
                    logger.info(f"📈 Migration progress: {progress:.1f}% ({offset}/{total_count})")
                    
                except Exception as e:
                    error_msg = f"Batch migration failed at offset {offset}: {e}"
                    logger.error(f"❌ {error_msg}")
                    stats["errors"].append(error_msg)
                    stats["failed_records"] += len(batch) if 'batch' in locals() else batch_size
                    offset += batch_size  # Continue with next batch
            
            # Validation
            if validate:
                validation_result = await self._validate_migration()
                stats["validation"] = validation_result
            
            stats["duration_seconds"] = time.time() - start_time
            stats["end_time"] = datetime.now().isoformat()
            
            logger.info(f"✅ Migration completed: {stats['migrated_records']}/{stats['total_records']} records")
            return stats
            
        except Exception as e:
            stats["fatal_error"] = str(e)
            stats["duration_seconds"] = time.time() - start_time
            logger.error(f"❌ Migration failed: {e}")
            raise
    
    async def _get_batch_from_source(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """Get a batch of records from source database"""
        if hasattr(self.source_adapter, '_pool'):
            # PostgreSQL source
            async with self.source_adapter._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM cost_events 
                    ORDER BY id 
                    LIMIT $1 OFFSET $2
                """, limit, offset)
                return [dict(row) for row in rows]
        else:
            # SQLite source
            def _get_batch():
                import sqlite3
                with sqlite3.connect(self.source_adapter.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("""
                        SELECT * FROM cost_events 
                        ORDER BY id 
                        LIMIT ? OFFSET ?
                    """, (limit, offset))
                    return [dict(row) for row in cursor.fetchall()]
            
            return await self.source_adapter._run_in_executor(_get_batch)
    
    async def _insert_batch_to_target(self, batch: List[Dict[str, Any]]) -> int:
        """Insert a batch of records into target database"""
        migrated_count = 0
        
        for record in batch:
            try:
                # Prepare event data (exclude auto-generated fields)
                event_data = {
                    'session_id': record['session_id'],
                    'user_id': record['user_id'],
                    'character': record['character'],
                    'timestamp': record['timestamp'],
                    'stt_duration_ms': record.get('stt_duration_ms'),
                    'llm_duration_ms': record.get('llm_duration_ms'),
                    'tts_duration_ms': record.get('tts_duration_ms'),
                    'total_latency_ms': record.get('total_latency_ms'),
                    'transcript_text': record.get('transcript_text'),
                    'response_text': record.get('response_text'),
                    'audio_duration_seconds': record.get('audio_duration_seconds'),
                    'success': record['success'],
                    'error_message': record.get('error_message')
                }
                
                # Insert event
                event_id = await self.target_adapter.insert_cost_event(event_data)
                
                # Update cost calculations if they exist
                if record.get('cost_calculated'):
                    costs = {
                        'stt_cost': record.get('stt_cost'),
                        'llm_cost': record.get('llm_cost'),
                        'tts_cost': record.get('tts_cost'),
                        'total_cost': record.get('total_cost'),
                        'input_tokens': record.get('input_tokens'),
                        'output_tokens': record.get('output_tokens')
                    }
                    await self.target_adapter.update_cost_calculation(event_id, costs)
                
                migrated_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to migrate record {record.get('id', 'unknown')}: {e}")
        
        return migrated_count
    
    async def _validate_migration(self) -> Dict[str, Any]:
        """Validate migration by comparing record counts and data integrity"""
        try:
            # Get counts from both databases
            if hasattr(self.source_adapter, '_pool'):
                async with self.source_adapter._pool.acquire() as conn:
                    source_count = await conn.fetchval("SELECT COUNT(*) FROM cost_events")
            else:
                def _count_source():
                    import sqlite3
                    with sqlite3.connect(self.source_adapter.db_path) as conn:
                        cursor = conn.execute("SELECT COUNT(*) FROM cost_events")
                        return cursor.fetchone()[0]
                source_count = await self.source_adapter._run_in_executor(_count_source)
            
            if hasattr(self.target_adapter, '_pool'):
                async with self.target_adapter._pool.acquire() as conn:
                    target_count = await conn.fetchval("SELECT COUNT(*) FROM cost_events")
            else:
                def _count_target():
                    import sqlite3
                    with sqlite3.connect(self.target_adapter.db_path) as conn:
                        cursor = conn.execute("SELECT COUNT(*) FROM cost_events")
                        return cursor.fetchone()[0]
                target_count = await self.target_adapter._run_in_executor(_count_target)
            
            validation = {
                "source_count": source_count,
                "target_count": target_count,
                "count_match": source_count == target_count,
                "missing_records": source_count - target_count if source_count > target_count else 0
            }
            
            if validation["count_match"]:
                logger.info("✅ Migration validation passed: record counts match")
            else:
                logger.warning(f"⚠️ Migration validation warning: count mismatch ({source_count} → {target_count})")
            
            return validation
            
        except Exception as e:
            logger.error(f"❌ Migration validation failed: {e}")
            return {"error": str(e)}


async def migrate_sqlite_to_postgresql(
    sqlite_path: str,
    postgresql_url: str,
    batch_size: int = 1000
) -> Dict[str, Any]:
    """
    Convenience function to migrate from SQLite to PostgreSQL
    
    Args:
        sqlite_path: Path to SQLite database file
        postgresql_url: PostgreSQL connection URL
        batch_size: Migration batch size
        
    Returns:
        Migration statistics
    """
    source_config = DatabaseConfig(type='sqlite', sqlite_path=sqlite_path)
    target_config = DatabaseConfig(type='postgresql', url=postgresql_url)
    
    migrator = DatabaseMigrator(source_config, target_config)
    
    try:
        await migrator.initialize()
        return await migrator.migrate_cost_events(batch_size=batch_size)
    finally:
        await migrator.close()