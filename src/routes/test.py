"""
Test routes for the Language Learning Flashcard App.

Handles testing and debugging functionality.
"""

from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, render_template

from src.config import SPREADSHEET_ID
from src.database import UserSpreadsheet, db
from src.gsheet import read_all_card_sets
from src.tts_service import TTSService
from src.user_manager import get_current_user

# Create blueprint
test_bp = Blueprint('test', __name__)

# Initialize TTS service for testing
tts_service = TTSService()


@test_bp.route('/test')
def test() -> dict[str, Any]:
    """Test basic functionality and return system status."""
    try:
        # Test Google Sheets access
        try:
            card_sets = read_all_card_sets(SPREADSHEET_ID)
            sheets_status = {
                'working': True,
                'card_sets_count': len(card_sets),
                'card_sets': [cs.name for cs in card_sets[:3]],  # First 3 for brevity
            }
        except Exception as e:
            sheets_status = {'working': False, 'error': str(e)}

        # Test TTS service
        try:
            tts_configured = tts_service.is_configured()
            if tts_configured:
                # Try a simple synthesis test
                test_audio = tts_service.generate_speech('teste')
                tts_status = {'configured': True, 'synthesis_test': test_audio is not None}
            else:
                tts_status = {'configured': False, 'synthesis_test': False}
        except Exception as e:
            tts_status = {'configured': False, 'synthesis_test': False, 'error': str(e)}

        return jsonify(
            {
                'success': True,
                'timestamp': str(datetime.now()),
                'services': {'google_sheets': sheets_status, 'text_to_speech': tts_status},
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@test_bp.route('/test-tts')
def test_tts():
    """Render TTS testing page."""
    return render_template('test_tts.html')


@test_bp.route('/test-properties')
def test_properties() -> dict[str, Any]:
    """Test the new properties column (Phase 1: simple text field)."""
    try:
        # Get current user (if logged in)
        user = get_current_user()
        if not user:
            return jsonify(
                {
                    'success': False,
                    'error': 'User not logged in. Please authenticate first.',
                    'note': 'This test requires an authenticated user with spreadsheets.',
                }
            )

        # Get user's first spreadsheet for testing
        spreadsheet = UserSpreadsheet.query.filter_by(user_id=user.id).first()
        if not spreadsheet:
            return jsonify(
                {
                    'success': False,
                    'error': 'No spreadsheets found for user.',
                    'note': 'Add a spreadsheet first, then test properties.',
                }
            )

        # Phase 1: Simple test - just show the current value and set a test value
        current_value = spreadsheet.properties

        # Test setting a simple JSON string
        test_json = '{"language":{"original":"ru","target":"pt","hint":"en"}}'
        spreadsheet.properties = test_json
        db.session.commit()

        # Read it back
        updated_value = spreadsheet.properties

        return jsonify(
            {
                'success': True,
                'phase': 'Phase 1 - Basic Column Test',
                'user_id': user.id,
                'spreadsheet_id': spreadsheet.spreadsheet_id,
                'test_results': {
                    'original_value': current_value,
                    'test_value_set': test_json,
                    'updated_value': updated_value,
                    'column_works': updated_value == test_json,
                },
                'note': 'Phase 1: Simple text column working correctly',
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@test_bp.route('/test-properties-phase2')
def test_properties_phase2() -> dict[str, Any]:
    """Test Phase 2 properties functionality with Pydantic models and language settings."""
    try:
        # Get current user (if logged in)
        user = get_current_user()
        if not user:
            return jsonify(
                {
                    'success': False,
                    'error': 'User not logged in. Please authenticate first.',
                    'note': 'This test requires an authenticated user with spreadsheets.',
                }
            )

        # Get user's active spreadsheet
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            return jsonify(
                {
                    'success': False,
                    'error': 'No active spreadsheet found for user.',
                    'note': 'Set an active spreadsheet first, then test Phase 2 properties.',
                }
            )

        # Test Phase 2: Pydantic model functionality
        from src.models import UserSpreadsheetProperty

        # Get current language settings
        current_language_settings = active_spreadsheet.get_language_settings()

        # Test setting new language settings
        test_language_settings = {'original': 'en', 'target': 'fr', 'hint': 'de'}

        # Save original settings for restoration
        original_settings = current_language_settings.copy()

        # Test setting language settings
        active_spreadsheet.set_language_settings(test_language_settings)
        db.session.commit()

        # Read back the settings
        updated_language_settings = active_spreadsheet.get_language_settings()

        # Test creating UserSpreadsheetProperty from scratch
        test_properties = UserSpreadsheetProperty(
            language={'original': 'es', 'target': 'it', 'hint': 'pt'}
        )

        # Test serialization
        serialized = test_properties.to_db_string()
        deserialized = UserSpreadsheetProperty.from_db_string(serialized)

        # Test setting full properties object
        active_spreadsheet.set_properties(test_properties)
        db.session.commit()

        # Read back full properties
        final_properties = active_spreadsheet.get_properties()

        # Restore original settings
        active_spreadsheet.set_language_settings(original_settings)
        db.session.commit()

        return jsonify(
            {
                'success': True,
                'phase': 'Phase 2 - Pydantic Models & Language Settings',
                'user_id': user.id,
                'spreadsheet_id': active_spreadsheet.spreadsheet_id,
                'test_results': {
                    'original_language_settings': original_settings,
                    'test_language_settings_applied': test_language_settings,
                    'updated_language_settings': updated_language_settings,
                    'language_settings_match': updated_language_settings == test_language_settings,
                    'pydantic_serialization': {
                        'original_object': test_properties.model_dump(),
                        'serialized_string': serialized,
                        'deserialized_object': deserialized.model_dump(),
                        'serialization_works': test_properties.model_dump()
                        == deserialized.model_dump(),
                    },
                    'full_properties_test': {
                        'set_properties_object': test_properties.model_dump(),
                        'retrieved_properties': final_properties.model_dump(),
                        'properties_match': test_properties.model_dump()
                        == final_properties.model_dump(),
                    },
                    'restored_original_settings': active_spreadsheet.get_language_settings(),
                },
                'note': 'Phase 2: Pydantic models and language settings working correctly',
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'phase': 'Phase 2 Test Failed'})


@test_bp.route('/test-enhanced-models')
def test_enhanced_models() -> dict[str, Any]:
    """Test enhanced models with SpreadsheetLanguages and Pydantic field defaults."""
    try:
        # Get current user (if logged in)
        user = get_current_user()
        if not user:
            return jsonify(
                {
                    'success': False,
                    'error': 'User not logged in. Please authenticate first.',
                    'note': 'This test requires an authenticated user with spreadsheets.',
                }
            )

        # Get user's active spreadsheet
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            return jsonify(
                {
                    'success': False,
                    'error': 'No active spreadsheet found for user.',
                    'note': 'Set an active spreadsheet first, then test enhanced models.',
                }
            )

        # Test enhanced models functionality
        from src.models import SpreadsheetLanguages, UserSpreadsheetProperty

        # Test 1: SpreadsheetLanguages model with Field defaults
        default_languages = SpreadsheetLanguages.get_default()

        # Test 2: Custom SpreadsheetLanguages
        custom_languages = SpreadsheetLanguages(original='de', target='fr', hint='es')

        # Test 3: SpreadsheetLanguages from_dict/to_dict
        lang_dict = {'original': 'ja', 'target': 'ko', 'hint': 'zh'}
        languages_from_dict = SpreadsheetLanguages.from_dict(lang_dict)
        dict_from_languages = languages_from_dict.to_dict()

        # Test 4: UserSpreadsheetProperty with field factory
        default_props = UserSpreadsheetProperty.get_default()

        # Test 5: UserSpreadsheetProperty with custom SpreadsheetLanguages
        custom_props = UserSpreadsheetProperty(language=custom_languages)

        # Test 6: Database integration - save original settings
        original_settings = active_spreadsheet.get_language_settings()

        # Test 7: Set language settings using enhanced models
        test_language_dict = {'original': 'it', 'target': 'es', 'hint': 'pt'}
        active_spreadsheet.set_language_settings(test_language_dict)
        db.session.commit()

        # Read back settings
        updated_settings = active_spreadsheet.get_language_settings()

        # Test 8: Set full properties with enhanced model
        test_properties = UserSpreadsheetProperty(
            language=SpreadsheetLanguages(original='nl', target='sv', hint='no')
        )

        active_spreadsheet.set_properties(test_properties)
        db.session.commit()

        # Read back full properties
        final_properties = active_spreadsheet.get_properties()
        final_language_settings = active_spreadsheet.get_language_settings()

        # Test 9: Backward compatibility - serialization/deserialization
        serialized = test_properties.to_db_string()
        deserialized = UserSpreadsheetProperty.from_db_string(serialized)

        # Test 10: Backward compatibility with old dict format
        old_format_json = '{"language": {"original": "ar", "target": "he", "hint": "en"}}'
        old_format_deserialized = UserSpreadsheetProperty.from_db_string(old_format_json)

        # Restore original settings
        active_spreadsheet.set_language_settings(original_settings)
        db.session.commit()

        return jsonify(
            {
                'success': True,
                'phase': 'Enhanced Models - SpreadsheetLanguages & Field Defaults',
                'user_id': user.id,
                'spreadsheet_id': active_spreadsheet.spreadsheet_id,
                'test_results': {
                    'default_languages': {
                        'model': default_languages.model_dump(),
                        'to_dict': default_languages.to_dict(),
                        'defaults_work': default_languages.original == 'ru'
                        and default_languages.target == 'pt',
                    },
                    'custom_languages': {
                        'model': custom_languages.model_dump(),
                        'to_dict': custom_languages.to_dict(),
                        'custom_values_work': custom_languages.original == 'de'
                        and custom_languages.target == 'fr',
                    },
                    'dict_conversion': {
                        'original_dict': lang_dict,
                        'from_dict_model': languages_from_dict.model_dump(),
                        'back_to_dict': dict_from_languages,
                        'roundtrip_works': lang_dict == dict_from_languages,
                    },
                    'default_properties': {
                        'model': default_props.model_dump(),
                        'field_factory_works': isinstance(
                            default_props.language, SpreadsheetLanguages
                        ),
                    },
                    'custom_properties': {
                        'model': custom_props.model_dump(),
                        'language_type_correct': isinstance(
                            custom_props.language, SpreadsheetLanguages
                        ),
                    },
                    'database_integration': {
                        'original_settings': original_settings,
                        'test_settings_applied': test_language_dict,
                        'updated_settings': updated_settings,
                        'settings_match': updated_settings == test_language_dict,
                        'final_language_settings': final_language_settings,
                        'final_properties_type': type(final_properties.language).__name__,
                    },
                    'backward_compatibility': {
                        'serialized_string': serialized,
                        'deserialized_model': deserialized.model_dump(),
                        'serialization_works': test_properties.model_dump()
                        == deserialized.model_dump(),
                        'old_format_json': old_format_json,
                        'old_format_deserialized': old_format_deserialized.model_dump(),
                        'old_format_works': old_format_deserialized.language.original == 'ar',
                    },
                    'restored_settings': active_spreadsheet.get_language_settings(),
                },
                'note': 'Enhanced models with SpreadsheetLanguages and Field defaults working correctly',
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'phase': 'Enhanced Models Test Failed'})


@test_bp.route('/test-enhanced-api')
def test_enhanced_api() -> dict[str, Any]:
    """Test the enhanced API endpoints with SpreadsheetLanguages model validation."""
    try:
        # Get current user (if logged in)
        user = get_current_user()
        if not user:
            return jsonify(
                {
                    'success': False,
                    'error': 'User not logged in. Please authenticate first.',
                    'note': 'This test requires an authenticated user with spreadsheets.',
                }
            )

        # Get user's active spreadsheet
        active_spreadsheet = user.get_active_spreadsheet()
        if not active_spreadsheet:
            return jsonify(
                {
                    'success': False,
                    'error': 'No active spreadsheet found for user.',
                    'note': 'Set an active spreadsheet first, then test enhanced API.',
                }
            )

        # Import Flask test client functionality
        import json as json_module

        from flask import current_app

        # Test 1: GET /api/language-settings (should work with enhanced model)
        with current_app.test_client() as client:
            # Set up session context (simplified for testing)
            with client.session_transaction() as sess:
                from src.session_manager import SessionKeys as sk

                sess[sk.USER_ID.value] = user.id
                sess[sk.AUTH_CREDENTIALS.value] = {'dummy': 'credentials'}

            # Test GET endpoint
            get_response = client.get('/api/language-settings')
            get_data = json_module.loads(get_response.data)

            # Test 2: POST /api/language-settings with valid data
            valid_language_data = {
                'language_settings': {'original': 'de', 'target': 'fr', 'hint': 'en'}
            }

            post_response = client.post(
                '/api/language-settings', json=valid_language_data, content_type='application/json'
            )
            post_data = json_module.loads(post_response.data)

            # Test 3: POST /api/language-settings with invalid data (should fail validation)
            invalid_language_data = {
                'language_settings': {
                    'original': 'x',  # Too short
                    'target': 'toolongcode',  # Too long
                    'hint': 'en',
                }
            }

            invalid_response = client.post(
                '/api/language-settings',
                json=invalid_language_data,
                content_type='application/json',
            )
            invalid_data = json_module.loads(invalid_response.data)

            # Test 4: POST /api/language-settings with duplicate values (should fail business logic)
            duplicate_language_data = {
                'language_settings': {
                    'original': 'en',
                    'target': 'en',  # Duplicate
                    'hint': 'en',  # Duplicate
                }
            }

            duplicate_response = client.post(
                '/api/language-settings',
                json=duplicate_language_data,
                content_type='application/json',
            )
            duplicate_data = json_module.loads(duplicate_response.data)

            # Test 5: POST /api/language-settings/validate endpoint
            validate_response = client.post(
                '/api/language-settings/validate',
                json={'language_settings': {'original': 'es', 'target': 'it', 'hint': 'pt'}},
                content_type='application/json',
            )
            validate_data = json_module.loads(validate_response.data)

            # Test 6: Validate endpoint with invalid data
            validate_invalid_response = client.post(
                '/api/language-settings/validate',
                json={'language_settings': {'original': 'a', 'target': 'b', 'hint': 'c'}},
                content_type='application/json',
            )
            validate_invalid_data = json_module.loads(validate_invalid_response.data)

            # Restore original settings
            if get_data.get('success'):
                original_settings = get_data['language_settings']
                client.post(
                    '/api/language-settings',
                    json={'language_settings': original_settings},
                    content_type='application/json',
                )

        return jsonify(
            {
                'success': True,
                'phase': 'Enhanced API - SpreadsheetLanguages Validation',
                'user_id': user.id,
                'spreadsheet_id': active_spreadsheet.spreadsheet_id,
                'test_results': {
                    'get_endpoint': {
                        'status_code': get_response.status_code,
                        'success': get_data.get('success', False),
                        'has_metadata': 'metadata' in get_data,
                        'model_version': get_data.get('metadata', {}).get('model_version'),
                        'has_validation_info': 'is_valid_configuration'
                        in get_data.get('metadata', {}),
                    },
                    'post_valid_endpoint': {
                        'status_code': post_response.status_code,
                        'success': post_data.get('success', False),
                        'has_metadata': 'metadata' in post_data,
                        'has_previous_settings': 'previous_settings'
                        in post_data.get('metadata', {}),
                    },
                    'post_invalid_validation': {
                        'status_code': invalid_response.status_code,
                        'success': invalid_data.get('success', True),  # Should be False
                        'has_validation_errors': 'validation_errors' in invalid_data,
                        'validation_errors_count': len(invalid_data.get('validation_errors', [])),
                        'has_expected_format': 'expected_format' in invalid_data,
                    },
                    'post_duplicate_validation': {
                        'status_code': duplicate_response.status_code,
                        'success': duplicate_data.get('success', True),  # Should be False
                        'error_mentions_duplicates': 'duplicate'
                        in duplicate_data.get('error', '').lower(),
                        'has_suggestion': 'suggestion' in duplicate_data,
                    },
                    'validate_endpoint': {
                        'status_code': validate_response.status_code,
                        'success': validate_data.get('success', False),
                        'valid': validate_data.get('valid', False),
                        'has_warnings': 'warnings' in validate_data,
                        'warnings_count': len(validate_data.get('warnings', [])),
                    },
                    'validate_invalid_endpoint': {
                        'status_code': validate_invalid_response.status_code,
                        'success': validate_invalid_data.get('success', False),
                        'valid': validate_invalid_data.get('valid', True),  # Should be False
                        'has_validation_errors': 'validation_errors' in validate_invalid_data,
                    },
                },
                'validation_summary': {
                    'get_works': get_response.status_code == 200 and get_data.get('success'),
                    'post_valid_works': post_response.status_code == 200
                    and post_data.get('success'),
                    'validation_catches_errors': invalid_response.status_code == 400
                    and not invalid_data.get('success'),
                    'business_logic_works': duplicate_response.status_code == 400
                    and not duplicate_data.get('success'),
                    'validate_endpoint_works': validate_response.status_code == 200
                    and validate_data.get('success'),
                    'validate_catches_errors': validate_invalid_response.status_code == 200
                    and not validate_invalid_data.get('valid'),
                },
                'note': 'Enhanced API with SpreadsheetLanguages model validation working correctly',
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'phase': 'Enhanced API Test Failed'})
