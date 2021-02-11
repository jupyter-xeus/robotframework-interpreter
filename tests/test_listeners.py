from robotframework_interpreter.listeners import ReturnValueListener


class CustomClass:
    def __str__(self):
        return "A custom class"


class RaisesOnCompare:
    def __eq__(self, _):
        raise ValueError("Not comparable")


def test_result_has_value():
    assert ReturnValueListener.has_value("string-value")
    assert ReturnValueListener.has_value(123)
    assert ReturnValueListener.has_value(CustomClass())
    assert ReturnValueListener.has_value(RaisesOnCompare())
    assert not ReturnValueListener.has_value(None)
    assert not ReturnValueListener.has_value("")
    assert not ReturnValueListener.has_value(b"")
