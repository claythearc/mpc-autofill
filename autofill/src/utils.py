import os
import sys
from math import floor
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree

import numpy as np
import ratelimit
import requests
from selenium.common.exceptions import NoAlertPresentException

import src.constants as constants

if TYPE_CHECKING:
    from driver import AutofillDriver


CURRDIR: str = os.path.dirname(os.path.realpath(sys.executable)) if getattr(sys, "frozen", False) else os.getcwd()

TEXT_BOLD = "\033[1m"
TEXT_END = "\033[0m"


class InvalidStateException(Exception):
    # TODO: recovery from invalid state?
    def __init__(self, state, expected_state):
        self.message = (
            f"Expected the driver to be in the state {TEXT_BOLD}{expected_state}{TEXT_END} but the driver is in the "
            f"state {TEXT_BOLD}{state}{TEXT_END}"
        )
        super().__init__(self.message)


class ValidationException(Exception):
    pass


@ratelimit.sleep_and_retry
@ratelimit.limits(calls=1, period=0.1)
def get_google_drive_file_name(drive_id: str) -> Optional[str]:
    """
    Retrieve the name for the Google Drive file identified by `drive_id`.
    """

    if not drive_id:
        return None
    try:
        with requests.post(
            constants.GoogleScriptsAPIs.image_name.value,
            data={"id": drive_id},
            timeout=30,
        ) as r_info:
            if r_info.status_code == 500:
                return None
            return r_info.json()["name"]
    except requests.exceptions.Timeout:
        return None


@ratelimit.sleep_and_retry
@ratelimit.limits(calls=1, period=0.1)
def download_google_drive_file(drive_id: str, file_path: str) -> bool:
    """
    Download the Google Drive file identified by `drive_id` to the specified `file_path`.
    Returns whether the request was successful or not.
    """

    with requests.post(
        constants.GoogleScriptsAPIs.image_content.value,
        data={"id": drive_id},
    ) as r_contents:
        if "<title>Error</title>" in r_contents.text:
            # error occurred while attempting to retrieve from Google API
            return False
        filecontents = r_contents.json()["result"]
        if len(filecontents) > 0:
            # Download the image
            with open(file_path, "wb") as f:
                f.write(np.array(filecontents, dtype=np.uint8))
                return True
    return False


def text_to_list(input_text: str) -> List[int]:
    """
    Helper function to translate strings like "[2, 4, 5, 6]" into sorted lists.
    """

    if not input_text:
        return []
    return sorted([int(x) for x in input_text.strip("][").replace(" ", "").split(",")])


def unpack_element(
    element: ElementTree.Element, tags: List[str], unpack_to_text=False
) -> Union[Dict[str, ElementTree.Element], Dict[str, str]]:
    """
    Unpacks `element` according to expected tags. Expected tags that don't have elements in `element` have
    value None in the return dictionary.
    If `unpack_to_text` is specified, returns the text of each element rather than the elements themselves.
    """

    element_dict = {x: None for x in tags}
    for x in element:
        if unpack_to_text:
            element_dict[x.tag] = x.text
        else:
            element_dict[x.tag] = x
    return element_dict


def image_directory() -> str:
    cards_folder = os.path.join(CURRDIR, "cards")
    if not os.path.exists(cards_folder):
        os.mkdir(cards_folder)
    return cards_folder


def file_exists(file_path: str) -> bool:
    return file_path != "" and os.path.isfile(file_path) and os.path.getsize(file_path) > 0


def alert_handler(func):
    """
    Function decorator which accepts an alert in the given Selenium driver if one is raised by the decorated function.
    """

    def wrapper(*args, **kwargs):
        try:
            autofill_driver: "AutofillDriver" = args[0]
            alert = autofill_driver.driver.switch_to.alert
            alert.accept()
        except NoAlertPresentException:
            pass
        return func(*args, **kwargs)

    return wrapper


def time_to_hours_minutes_seconds(t) -> Tuple[int, int, int]:
    hours = int(floor(t / 3600))
    mins = int(floor(t / 60) - hours * 60)
    secs = int(t - (mins * 60) - (hours * 3600))
    return hours, mins, secs
