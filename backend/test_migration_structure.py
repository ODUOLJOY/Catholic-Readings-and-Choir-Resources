"""Verify migration SQL structure without running it."""
import sys
import importlib

def verify_migration_structure():
    """Verify the migration file has correct structure."""
    print("=== Verifying Migration Structure ===")
    
    try:
        # Import the migration using importlib
        migration_module = importlib.import_module("migrations.versions.20261002_08_reading_references")
        
        revision = getattr(migration_module, "revision")
        down_revision = getattr(migration_module, "down_revision")
        upgrade = getattr(migration_module, "upgrade")
        downgrade = getattr(migration_module, "downgrade")
        _upgrade_liturgical_day = getattr(migration_module, "_upgrade_liturgical_day")
        _downgrade_liturgical_day = getattr(migration_module, "_downgrade_liturgical_day")
        _recreate_reading_sets_table = getattr(migration_module, "_recreate_reading_sets_table")
        _restore_reading_sets_table = getattr(migration_module, "_restore_reading_sets_table")
        _create_reading_references_table = getattr(migration_module, "_create_reading_references_table")
        _drop_reading_references_table = getattr(migration_module, "_drop_reading_references_table")
        
        # Check revision info
        assert revision == "20261002_08", f"Wrong revision: {revision}"
        assert down_revision == "20261002_07", f"Wrong down_revision: {down_revision}"
        print("[OK] Revision IDs correct")
        
        # Check functions exist
        assert callable(_upgrade_liturgical_day), "_upgrade_liturgical_day not callable"
        assert callable(_downgrade_liturgical_day), "_downgrade_liturgical_day not callable"
        assert callable(_recreate_reading_sets_table), "_recreate_reading_sets_table not callable"
        assert callable(_restore_reading_sets_table), "_restore_reading_sets_table not callable"
        assert callable(_create_reading_references_table), "_create_reading_references_table not callable"
        assert callable(_drop_reading_references_table), "_drop_reading_references_table not callable"
        print("[OK] Migration functions exist")
        
        # Check upgrade/downgrade exist
        assert callable(upgrade), "upgrade not callable"
        assert callable(downgrade), "downgrade not callable"
        print("[OK] upgrade/downgrade functions exist")
        
        print("\n=== Migration Structure Verification PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n=== Migration Structure Verification FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_migration_structure()
    sys.exit(0 if success else 1)
