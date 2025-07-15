/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VoiceUploadResponse = {
    properties: {
        transcription: {
            type: 'string',
            isRequired: true,
        },
        tasks: {
            type: 'array',
            contains: {
                type: 'dictionary',
                contains: {
                    properties: {
                    },
                },
            },
            isRequired: true,
        },
        id: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
