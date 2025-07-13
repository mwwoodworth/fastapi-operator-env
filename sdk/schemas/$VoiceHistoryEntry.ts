/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VoiceHistoryEntry = {
    properties: {
        id: {
            type: 'string',
            isRequired: true,
        },
        filename: {
            type: 'string',
            isRequired: true,
        },
        transcript: {
            type: 'string',
            isRequired: true,
        },
        timestamp: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
