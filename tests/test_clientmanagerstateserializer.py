from nose.tools import raises
from mock import MagicMock, PropertyMock
import json

from remotespark.livyclientlib.clientmanagerstateserializer import ClientManagerStateSerializer


@raises(AssertionError)
def test_serializer_throws_none_factory():
    ClientManagerStateSerializer(None)


def test_deserialize_not_empty():
    session = MagicMock()
    session.is_final_status.return_value = False
    reader_writer = MagicMock()
    reader_writer.read_lines.return_value = """{
  "clients": [
    {
      "name": "py",
      "id": "1",
      "sqlcontext": true,
      "kind": "pyspark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    },
    {
      "name": "sc",
      "id": "2",
      "sqlcontext": false,
      "kind": "spark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    }
  ]
}
"""
    serializer = ClientManagerStateSerializer(reader_writer)
    serializer._create_livy_session = MagicMock(return_value=session)
    serializer._create_livy_client = MagicMock()

    deserialized = serializer.deserialize_state()

    assert len(deserialized) == 2

    (name, client) = deserialized[0]
    assert name == "py"
    serializer._create_livy_session.assert_any_call("url=https://mysite.com/livy;username=user;password=pass",
                                                    {"kind":"pyspark"}, serializer._ipython_display, "1", True)
    serializer._create_livy_client.assert_any_call(session)

    (name, client) = deserialized[1]
    assert name == "sc"
    serializer._create_livy_session.assert_any_call("url=https://mysite.com/livy;username=user;password=pass",
                                                     {"kind":"spark"}, serializer._ipython_display, "2", False)
    serializer._create_livy_client.assert_any_call(session)


def test_deserialize_not_empty_but_dead():
    session = MagicMock()
    session.is_final_status.return_value = True
    reader_writer = MagicMock()
    reader_writer.read_lines.return_value = """{
  "clients": [
    {
      "name": "py",
      "id": "1",
      "sqlcontext": true,
      "kind": "pyspark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    },
    {
      "name": "sc",
      "id": "2",
      "sqlcontext": false,
      "kind": "spark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    }
  ]
}
"""
    serializer = ClientManagerStateSerializer(reader_writer)
    serializer._create_livy_session = MagicMock(return_value=session)
    serializer._create_livy_client = MagicMock()

    deserialized = serializer.deserialize_state()

    assert len(deserialized) == 0
    serializer._create_livy_session.assert_no_called()
    serializer._create_livy_client.assert_no_called()


def test_deserialize_not_empty_but_error():
    session = MagicMock()
    status_property = PropertyMock()
    status_property.side_effect = ValueError()
    type(session).status = status_property
    reader_writer = MagicMock()
    reader_writer.read_lines.return_value = """{
  "clients": [
    {
      "name": "py",
      "id": "1",
      "sqlcontext": true,
      "kind": "pyspark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    },
    {
      "name": "sc",
      "id": "2",
      "sqlcontext": false,
      "kind": "spark",
      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
      "version": "0.0.0"
    }
  ]
}
"""
    serializer = ClientManagerStateSerializer(reader_writer)
    serializer._create_livy_session = MagicMock(return_value=session)
    serializer._create_livy_client = MagicMock()

    deserialized = serializer.deserialize_state()

    assert len(deserialized) == 0
    serializer._create_livy_session.assert_no_called()
    serializer._create_livy_session.assert_no_called()


def test_deserialize_empty():
    reader_writer = MagicMock()
    reader_writer.read_lines.return_value = ""
    serializer = ClientManagerStateSerializer(reader_writer)
    serializer._create_livy_session = MagicMock(side_effect=ValueError)
    serializer._create_livy_client = MagicMock(side_effect=ValueError)

    deserialized = serializer.deserialize_state()

    assert len(deserialized) == 0


def test_serialize_not_empty():
    # Prepare data to serialize
    reader_writer = MagicMock()
    client1 = MagicMock()
    client1.serialize.return_value = {"id": "1", "sqlcontext": True, "kind": "pyspark",
                                      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
                                      "version": "0.0.0"}
    client2 = MagicMock()
    client2.serialize.return_value = {"id": "2", "sqlcontext": False, "kind": "spark",
                                      "connectionstring": "url=https://mysite.com/livy;username=user;password=pass",
                                      "version": "0.0.0"}
    serializer = ClientManagerStateSerializer(reader_writer)

    # Call serialization
    serializer.serialize_state({"py": client1, "sc": client2})

    # Verify write was called with following string
    expected_str = '{"clients": [{"name": "py", "connectionstring": "url=https://mysite.com/livy;username=user;p' \
                   'assword=pass", "version": "0.0.0", "kind": "pyspark", "sqlcontext": true, "id": "1"}, {"n' \
                   'ame": "sc", "connectionstring": "url=https://mysite.com/livy;username=user;password=pass", "ve' \
                   'rsion": "0.0.0", "kind": "spark", "sqlcontext": false, "id": "2"}]}'
    expected_dict = json.loads(expected_str)
    call_list = reader_writer.overwrite_with_line.call_args_list
    assert len(call_list) == 1
    args, kwargs = call_list[0]
    called_with = json.loads(args[0])

    # == comparison doesn't work on test even though it works on cmd
    # created helper methods below meanwhile
    assert _compare_dicts(expected_dict, called_with)


def _compare_dicts(d1, d2):
    if sorted(d1.keys()) != sorted(d2.keys()):
        return False

    for key in list(d1.keys()):
        v1 = d1[key]
        v2 = d2[key]

        if type(v1) is list:
            if type(v2) is not list:
                return False
            _compare_list_dicts(v1, v2)
        else:
            if v1 != v2:
                return False

    return True


def _compare_list_dicts(l1, l2):
    assert len(l1) == len(l2)
    for i in range(len(l1)):
        found = False
        e1 = l1[i]

        for j in range(len(l2)):
            e2 = l2[j]
            if _compare_dicts(e1, e2):
                found = True
                break

        if not found:
            raise AssertionError("{} was not found in list {}.".format(str(e1), str(l1)))
