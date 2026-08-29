from contacts_manager import ContactsManager


def test_add_or_update_creates_new_contact(tmp_path):
    manager = ContactsManager(str(tmp_path))

    result = manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")

    assert "Saved Jane Doe" in result
    contacts = manager.list_contacts()
    assert len(contacts) == 1
    assert contacts[0]["name"] == "Jane Doe"
    assert contacts[0]["channels"]["whatsapp"] == "+15550001111"


def test_add_or_update_merges_channels_for_same_contact(tmp_path):
    manager = ContactsManager(str(tmp_path))

    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")
    manager.add_or_update("jane doe", "jane@example.com", "email")

    contact = manager.find("Jane Doe")
    assert contact["channels"]["whatsapp"] == "+15550001111"
    assert contact["channels"]["email"] == "jane@example.com"


def test_add_or_update_requires_name_and_recipient(tmp_path):
    manager = ContactsManager(str(tmp_path))

    result = manager.add_or_update("", "", "whatsapp")

    assert "required" in result.lower()
    assert manager.list_contacts() == []


def test_remove_single_platform_keeps_other_channels(tmp_path):
    manager = ContactsManager(str(tmp_path))
    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")
    manager.add_or_update("Jane Doe", "jane@example.com", "email")

    result = manager.remove("Jane Doe", "whatsapp")

    assert "Removed" in result
    contact = manager.find("Jane Doe")
    assert "whatsapp" not in contact["channels"]
    assert contact["channels"]["email"] == "jane@example.com"


def test_remove_without_platform_deletes_entire_contact(tmp_path):
    manager = ContactsManager(str(tmp_path))
    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")

    manager.remove("Jane Doe")

    assert manager.find("Jane Doe") is None


def test_remove_nonexistent_contact_reports_not_found(tmp_path):
    manager = ContactsManager(str(tmp_path))

    result = manager.remove("Ghost")

    assert "not found" in result.lower()


def test_find_matches_partial_name(tmp_path):
    manager = ContactsManager(str(tmp_path))
    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")

    contact = manager.find("jane")

    assert contact is not None
    assert contact["name"] == "Jane Doe"


def test_resolve_falls_back_to_whatsapp(tmp_path):
    manager = ContactsManager(str(tmp_path))
    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")

    recipient = manager.resolve("Jane Doe", "sms")

    assert recipient == "+15550001111"


def test_resolve_returns_none_for_unknown_contact(tmp_path):
    manager = ContactsManager(str(tmp_path))

    assert manager.resolve("Ghost") is None


def test_format_contacts_reports_no_contacts(tmp_path):
    manager = ContactsManager(str(tmp_path))

    assert manager.format_contacts() == "No contacts saved."


def test_contacts_persist_across_manager_instances(tmp_path):
    manager = ContactsManager(str(tmp_path))
    manager.add_or_update("Jane Doe", "+15550001111", "whatsapp")

    reloaded = ContactsManager(str(tmp_path))

    assert reloaded.find("Jane Doe") is not None
