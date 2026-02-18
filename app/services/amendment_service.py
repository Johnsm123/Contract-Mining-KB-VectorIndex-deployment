from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AmendmentService:
    """Handle contract amendments - GCS based"""
    
    async def create_amendment(self, contract_id: str, user_id: str, changes: List[Dict]) -> Dict:
        """Create new amendment"""
        logger.info(f"Creating amendment for contract {contract_id}")
        return {
            "amendment_id": f"amend_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "created",
            "changes_count": len(changes),
            "created_at": datetime.now().isoformat()
        }
    
    async def get_amendment_details(self, amendment_id: str, user_id: str) -> Dict:
        """Get amendment details"""
        return {"amendment_id": amendment_id, "status": "draft"}
    
    async def list_amendments(self, contract_id: str, user_id: str) -> List[Dict]:
        """List amendments"""
        return []

amendment_service = AmendmentService()

class AmendmentService:
    """Handle contract amendments with version control"""
    
    async def create_amendment(
        self, 
        contract_id: str, 
        user_id: str,
        changes: List[Dict]
    ) -> Dict:
        """Create new amendment with line changes"""
        
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Get contract
                contract = await conn.fetchrow(
                    "SELECT * FROM contracts WHERE contract_id = $1 AND user_id = $2",
                    contract_id, user_id
                )
                
                if not contract:
                    raise Exception("Contract not found")
                
                # Create amendment
                amendment_id = await conn.fetchval("""
                    INSERT INTO amendments (
                        contract_id, user_id, title, description, status
                    ) VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, contract['id'], user_id, 
                    f"Amendment {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
                    "Contract modifications", "draft")
                
                # Create line changes
                for change in changes:
                    await conn.execute("""
                        INSERT INTO amendment_changes (
                            amendment_id, line_number, action, old_text, new_text
                        ) VALUES ($1, $2, $3, $4, $5)
                    """, amendment_id, change['line_number'], change['action'],
                        change.get('old_text'), change.get('new_text'))
                    
                    # Update contract lines based on action
                    if change['action'] == 'replace':
                        await conn.execute("""
                            UPDATE contract_lines 
                            SET line_text = $1 
                            WHERE contract_id = $2 AND line_number = $3
                        """, change['new_text'], contract['id'], change['line_number'])
                    
                    elif change['action'] == 'add':
                        await conn.execute("""
                            INSERT INTO contract_lines (
                                contract_id, line_number, line_text, page_number
                            ) VALUES ($1, $2, $3, $4)
                        """, contract['id'], change['line_number'], 
                            change['new_text'], change.get('page_number', 1))
                
                logger.info(f"Created amendment {amendment_id} with {len(changes)} changes")
                
                return {
                    "amendment_id": str(amendment_id),
                    "status": "created",
                    "changes_count": len(changes),
                    "created_at": datetime.now().isoformat()
                }
    
    async def get_amendment_details(self, amendment_id: str, user_id: str) -> Dict:
        """Get amendment with all changes"""
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            amendment = await conn.fetchrow(
                "SELECT * FROM amendments WHERE id = $1", 
                uuid.UUID(amendment_id)
            )
            
            if not amendment:
                raise Exception("Amendment not found")
            
            # Verify user owns contract
            contract = await conn.fetchrow(
                "SELECT * FROM contracts WHERE id = $1 AND user_id = $2",
                amendment['contract_id'], user_id
            )
            
            if not contract:
                raise Exception("Unauthorized")
            
            changes = await conn.fetch(
                "SELECT * FROM amendment_changes WHERE amendment_id = $1 ORDER BY line_number",
                uuid.UUID(amendment_id)
            )
            
            return {
                "amendment_id": str(amendment['id']),
                "contract_id": contract['contract_id'],
                "contract_name": contract['name'],
                "status": amendment['status'],
                "title": amendment['title'],
                "changes": [dict(c) for c in changes],
                "created_at": amendment['created_at'].isoformat()
            }
    
    async def list_amendments(self, contract_id: str, user_id: str) -> List[Dict]:
        """List all amendments for a contract"""
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            contract = await conn.fetchrow(
                "SELECT * FROM contracts WHERE contract_id = $1 AND user_id = $2",
                contract_id, user_id
            )
            
            if not contract:
                raise Exception("Contract not found")
            
            amendments = await conn.fetch("""
                SELECT id, title, status, created_at,
                       (SELECT COUNT(*) FROM amendment_changes WHERE amendment_id = amendments.id) as changes_count
                FROM amendments 
                WHERE contract_id = $1 
                ORDER BY created_at DESC
            """, contract['id'])
            
            return [dict(a) for a in amendments]

# Global instance
amendment_service = AmendmentService()
