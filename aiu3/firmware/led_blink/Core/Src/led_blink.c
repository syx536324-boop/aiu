/* Responsibility: hold the active-low PC13 board LED on. */
#include "led_blink.h"
#include "main.h"

void Led_SetOn(void)
{
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
}